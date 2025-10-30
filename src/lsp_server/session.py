from pathlib import Path

from src.common.opened_file import OpenedFile
from src.common.vars import log
from src.configs.clangd_config import ClangdConfig
from src.lsp_server.engine import LspEngine
import sansio_lsp_client as lsp


class LspSession:
    def __init__(self, path_to_project: str):
        self.project_path = Path(path_to_project).resolve()
        self.engine = LspEngine(str(self.project_path), ClangdConfig())

    def __enter__(self):
        self.engine.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.engine.__exit__(exc_type, exc_value, traceback)

    def tick(self):
        self.engine._send()

    def _resolve_uri(self, file_path: str) -> str:
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        return file_path.resolve().as_uri()

    def open_file(self, path):
        if not Path(path).is_absolute():
            path = self.project_path / path
        else:
            path = Path(path)
        path_obj = path.resolve()
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
        if uri not in self.engine.opened_files:
            log(f"File {file_path} is not open.")
            return
        del self.engine.opened_files[uri]
        self.engine.lsp_client.did_close(lsp.TextDocumentIdentifier(uri=uri))
        self.tick()
        log(f"Closed file: {file_path}")

    def on_text_change(self, file_path: str, new_content: str):
        uri = self._resolve_uri(file_path)
        if uri not in self.engine.opened_files:
            log(f"Cannot change text of a file that is not open: {file_path}")
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
        if uri not in self.engine.opened_files:
            log(f"Cannot change text of a file that is not open: {file_path}")
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
        if uri not in self.engine.opened_files:
            log(f"File {file_path} is not open.")
            return
        file_obj = self.engine.opened_files[uri]
        file_obj.save()
        self.engine.lsp_client.did_save(
            lsp.TextDocumentIdentifier(uri=uri), text=str(file_obj)
        )
        self.tick()
        log(f"Saved file: {file_path}")

    def get_completion(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.completion(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.Completion):
                return response.completion_list
            log(f"Completion error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for completion: {e}")
        return None

    def goto_definition(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.definition(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.Definition):
                return response.result
            log(f"Definition error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for definition: {e}")
        return None

    def goto_declaration(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.declaration(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.Declaration):
                return response.result
            log(f"Declaration error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for declaration: {e}")
        return None

    def goto_implementation(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.implementation(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.Implementation):
                return response.result
            log(f"Implementation error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for implementation: {e}")
        return None

    def goto_type_definition(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.typeDefinition(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.TypeDefinition):
                return response.result
            log(f"Type definition error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for type definition: {e}")
        return None

    def find_references(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.references(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.References):
                return response.result
            log(f"References error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for references: {e}")
        return None

    def rename_symbol(self, file_path: str, line: int, character: int, new_name: str):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.rename(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            ),
            new_name,
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.WorkspaceEdit):
                return response
            log(f"Rename error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for rename: {e}")
        return None

    def format_document(self, file_path: str):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.formatting(
            text_document=lsp.TextDocumentIdentifier(uri=uri),
            options=lsp.FormattingOptions(tabSize=4, insertSpaces=True),
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.DocumentFormatting) and response.result:
                file_obj = self.engine.opened_files[uri]
                for edit in sorted(
                    response.result,
                    key=lambda e: (e.range.start.line, e.range.start.character),
                    reverse=True,
                ):
                    file_obj.apply_edit(edit)
                file_obj.save()
                self.on_text_change(file_path, str(file_obj))
                log(f"Document formatted: {file_path}")
                return True
            log(f"Formatting error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for formatting: {e}")
        return False

    def format_range(self, file_path: str, range_to_format: lsp.Range):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.rangeFormatting(
            lsp.TextDocumentIdentifier(uri=uri),
            range_to_format,
            lsp.FormattingOptions(tabSize=4, insertSpaces=True),
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.DocumentFormatting) and response.result:
                return response.result
            log(f"Range formatting error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for range formatting: {e}")
        return None

    def get_hover(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.hover(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.Hover):
                return response.contents
            log(f"Hover error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for hover: {e}")
        return None

    def get_signature_help(self, file_path: str, line: int, character: int):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.signatureHelp(
            lsp.TextDocumentPosition(
                textDocument=lsp.TextDocumentIdentifier(uri=uri),
                position=lsp.Position(line=line, character=character),
            )
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.SignatureHelp):
                return response
            log(f"Signature help error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for signature help: {e}")
        return None

    def get_document_symbols(self, file_path: str):
        uri = self._resolve_uri(file_path)
        msg_id = self.engine.lsp_client.documentSymbol(
            lsp.TextDocumentIdentifier(uri=uri)
        )
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.MDocumentSymbols):
                return response.result
            log(f"Document symbols error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for document symbols: {e}")
        return None

    def search_workspace_symbols(self, query: str):
        msg_id = self.engine.lsp_client.workspace_symbol(query)
        self.tick()
        try:
            response = self.engine.wait_for_response(msg_id, timeout=2.0)
            if isinstance(response, lsp.MWorkspaceSymbols):
                return response.result
            log(f"Workspace symbols error: {response.message}")
        except TimeoutError as e:
            log(f"Timeout waiting for workspace symbols: {e}")
        return None

    def get_diagnostics(self, file_path: str = None):
        if file_path:
            uri = self._resolve_uri(file_path)
            return self.engine.diagnostics.get(uri, [])
        return self.engine.diagnostics
