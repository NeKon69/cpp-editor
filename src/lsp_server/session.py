from pathlib import Path
from typing import Optional, List, Any, Dict
from src.common.opened_file import OpenedFile
from src.common.vars import log
from src.configs.clangd_config import ClangdConfig
from src.lsp_server.engine import LspEngine
import sansio_lsp_client as lsp


class LspSession:
    def __init__(self, path_to_project: str):
        self.project_path = Path(path_to_project).resolve()
        self.engine = LspEngine(str(self.project_path), ClangdConfig())
        self._pending_requests: Dict[int, str] = {}

    def __enter__(self):
        self.engine.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.engine.__exit__(exc_type, exc_value, traceback)

    def tick(self):
        self.engine._send()

    def _resolve_uri(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.is_absolute():
            path = self.project_path / path
        return path.resolve().as_uri()

    def _check_file_open(self, uri: str, file_path: str) -> bool:
        if uri not in self.engine.opened_files:
            log(f"File {file_path} is not open.")
            return False
        return True

    def open_file(self, path: str):
        path_obj = Path(path)
        if not path_obj.is_absolute():
            path_obj = self.project_path / path_obj
        path_obj = path_obj.resolve()
        uri = path_obj.as_uri()

        file = OpenedFile(str(path_obj))
        self.engine.opened_files[uri] = file
        self.engine.lsp_client.did_open(
            lsp.TextDocumentItem(
                uri=uri,
                languageId="cpp",
                version=file.version,
                text=str(file),
            )
        )
        self.tick()
        log(f"Opened file: {path_obj}")

    def close_file(self, file_path: str):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return
        del self.engine.opened_files[uri]
        self.engine.lsp_client.did_close(lsp.TextDocumentIdentifier(uri=uri))
        self.tick()
        log(f"Closed file: {file_path}")

    def on_text_change(self, file_path: str, new_content: str, is_full: bool = True):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return

        file_obj = self.engine.opened_files[uri]
        file_obj.contents = new_content.splitlines(True)
        file_obj.version += 1

        self.engine.lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=uri, version=file_obj.version
            ),
            content_changes=[
                lsp.TextDocumentContentChangeEvent.whole_document_change(new_content)
            ],
        )
        self.tick()

    def on_incremental_change(
        self, file_path: str, change_range: lsp.Range, new_text: str
    ):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return

        file_obj = self.engine.opened_files[uri]
        file_obj.version += 1

        change_event = lsp.TextDocumentContentChangeEvent.range_change(
            change_start=change_range.start,
            change_end=change_range.end,
            change_text=new_text,
            old_text=str(file_obj),
        )

        self.engine.lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(
                uri=uri, version=file_obj.version
            ),
            content_changes=[change_event],
        )
        self.tick()

    def save_file(self, file_path: str):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return

        file_obj = self.engine.opened_files[uri]
        file_obj.save()
        self.engine.lsp_client.did_save(
            lsp.TextDocumentIdentifier(uri=uri), text=str(file_obj)
        )
        self.tick()
        log(f"Saved file: {file_path}")

    def _send_lsp_request(self, msg_id: int, timeout: float = 2.0) -> Optional[Any]:
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=timeout)
            return response
        except TimeoutError as e:
            log(f"LSP timeout: {e}")
            return None

    def get_completion(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = self.engine.lsp_client.completion(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, lsp.Completion):
            return response.completion_list
        return None

    def goto_definition(self, file_path: str, line: int, character: int):
        return self._goto_location(
            file_path,
            line,
            character,
            self.engine.lsp_client.definition,
            lsp.Definition,
        )

    def goto_declaration(self, file_path: str, line: int, character: int):
        return self._goto_location(
            file_path,
            line,
            character,
            self.engine.lsp_client.declaration,
            lsp.Declaration,
        )

    def goto_implementation(self, file_path: str, line: int, character: int):
        return self._goto_location(
            file_path,
            line,
            character,
            self.engine.lsp_client.implementation,
            lsp.Implementation,
        )

    def goto_type_definition(self, file_path: str, line: int, character: int):
        return self._goto_location(
            file_path,
            line,
            character,
            self.engine.lsp_client.typeDefinition,
            lsp.TypeDefinition,
        )

    def _goto_location(
        self, file_path: str, line: int, character: int, method, expected_type
    ):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = method(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, expected_type):
            return response.result
        return None

    def find_references(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = self.engine.lsp_client.references(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, lsp.References):
            return response.result
        return None

    def rename_symbol(self, file_path: str, line: int, character: int, new_name: str):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = self.engine.lsp_client.rename(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            ),
            new_name,
        )
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, lsp.WorkspaceEdit):
            return response
        return None

    def format_document(self, file_path: str) -> bool:
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return False

        msg_id = self.engine.lsp_client.formatting(
            text_document=lsp.TextDocumentIdentifier(uri=uri),
            options=lsp.FormattingOptions(tabSize=4, insertSpaces=True),
        )
        response = self._send_lsp_request(msg_id)
        if (
            response
            and isinstance(response, lsp.DocumentFormatting)
            and response.result
        ):
            file_obj = self.engine.opened_files[uri]
            for edit in sorted(
                response.result,
                key=lambda e: (e.range.start.line, e.range.start.character),
                reverse=True,
            ):
                file_obj.apply_edit(edit)
            file_obj.save()
            log(f"Document formatted: {file_path}")
            return True
        return False

    def format_range(self, file_path: str, range_to_format: lsp.Range):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = self.engine.lsp_client.rangeFormatting(
            lsp.TextDocumentIdentifier(uri=uri),
            range_to_format,
            lsp.FormattingOptions(tabSize=4, insertSpaces=True),
        )
        response = self._send_lsp_request(msg_id)
        if (
            response
            and isinstance(response, lsp.DocumentFormatting)
            and response.result
        ):
            return response.result
        return None

    def get_hover(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = self.engine.lsp_client.hover(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, lsp.Hover):
            return response.contents
        return None

    def get_signature_help(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = self.engine.lsp_client.signatureHelp(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, lsp.SignatureHelp):
            return response
        return None

    def get_document_symbols(self, file_path: str):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        msg_id = self.engine.lsp_client.documentSymbol(
            lsp.TextDocumentIdentifier(uri=uri)
        )
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, lsp.MDocumentSymbols):
            return response.result
        return None

    def search_workspace_symbols(self, query: str):
        msg_id = self.engine.lsp_client.workspace_symbol(query)
        response = self._send_lsp_request(msg_id)
        if response and isinstance(response, lsp.MWorkspaceSymbols):
            return response.result
        return None

    def get_diagnostics(self, file_path: Optional[str] = None) -> Dict[str, List]:
        if file_path:
            uri = self._resolve_uri(file_path)
            return {uri: self.engine.diagnostics.get(uri, [])}
        return dict(self.engine.diagnostics)

    def get_code_actions(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        if not self._check_file_open(uri, file_path):
            return None

        try:
            msg_id = self.engine.lsp_client.sendRequest(
                method="textDocument/codeAction",
                params={
                    "textDocument": {"uri": uri},
                    "range": {
                        "start": {"line": line, "character": character},
                        "end": {"line": line, "character": character},
                    },
                    "context": {"diagnostics": []},
                },
            )
            response = self._send_lsp_request(msg_id, timeout=2.0)

            if response and hasattr(response, "result") and response.result:
                return response.result

            return None
        except Exception as e:
            log(f"lsp: error getting code actions: {e}")
            return None
