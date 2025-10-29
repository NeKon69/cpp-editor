from typing import List
import subprocess
import time
import os
import json
from pathlib import Path
import threading
import sansio_lsp_client as lsp

log = print


class ClangdNotFoundError(FileNotFoundError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class OpenedFile:
    def __init__(self, path: str):
        self.path: str = path
        self.contents: List[str] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.contents = f.readlines()
        except FileNotFoundError:
            with open(path, "w", encoding="utf-8") as f:
                pass
            log(f"Created new file: {path}")
        except (IOError, PermissionError) as e:
            log(f"Error reading file {path}: {e}")
        except Exception as e:
            log(f"An unexpected error occurred while opening {path}: {e}")

    def __str__(self):
        return "".join(self.contents)

    def insert(self, position: lsp.Position, text: str):
        lines_to_insert = text.splitlines(True)
        if not lines_to_insert:
            return
        while position.line >= len(self.contents):
            self.contents.append("\n")
        if self.contents and not self.contents[-1].endswith("\n"):
            self.contents[-1] += "\n"
        original_line = self.contents[position.line]
        original_line_content = original_line.rstrip("\n")
        char_pos = min(position.character, len(original_line_content))
        before_text = original_line_content[:char_pos]
        after_text = original_line_content[char_pos:]
        lines_to_insert[0] = before_text + lines_to_insert[0]
        if not lines_to_insert[-1].endswith("\n"):
            lines_to_insert[-1] += after_text
        else:
            lines_to_insert.append(after_text + "\n")
        self.contents[position.line : position.line + 1] = lines_to_insert

    def apply_edit(self, edit: lsp.TextEdit):
        start = edit.range.start
        end = edit.range.end
        new_lines = edit.newText.splitlines(True)
        if not new_lines:
            new_lines = [""]
        line_before = self.contents[start.line][: start.character]
        line_after = self.contents[end.line][end.character :]
        new_lines[0] = line_before + new_lines[0]
        new_lines[-1] = new_lines[-1].rstrip("\r\n") + line_after
        self.contents[start.line : end.line + 1] = new_lines

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("".join(self.contents))
            log(f"File saved: {self.path}")
        except (IOError, PermissionError) as e:
            log(f"Error saving file {self.path}: {e}")


class ClangdProcess:
    def __init__(self, project_path: str, lsp_client=None):
        self.project_path = project_path
        self.process = None
        self.lsp_client = lsp_client

    def __enter__(self):
        try:
            self.process = subprocess.Popen(
                ["clangd", "-log=verbose", "--background-index"],
                cwd=self.project_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            os.set_blocking(self.process.stdout.fileno(), False)
            os.set_blocking(self.process.stderr.fileno(), False)
        except FileNotFoundError as e:
            raise ClangdNotFoundError() from e
        except Exception as e:
            raise RuntimeError(f"Wasn't able to start clangd: {e}") from e
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.process or self.process.poll() is not None:
            return
        if self.lsp_client:
            try:
                if self.lsp_client.state == lsp.ClientState.NORMAL:
                    self.lsp_client.shutdown()
                    data = self.lsp_client.send()
                    if data:
                        self.process.stdin.write(data)
                        self.process.stdin.flush()
                    time.sleep(0.1)

                if self.lsp_client.state == lsp.ClientState.SHUTDOWN:
                    self.lsp_client.exit()
                    data = self.lsp_client.send()
                    if data:
                        self.process.stdin.write(data)
                        self.process.stdin.flush()
                    time.sleep(0.1)
            except (IOError, BrokenPipeError, AssertionError) as e:
                self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()


class BaseConfig:
    def get_launch_commands(self) -> list[str]:
        pass

    def get_cfg(self, project_path) -> list[str]:
        pass

    def on_pre_init(self, project_path):
        pass


class ClangdConfig(BaseConfig):
    def get_launch_commands(self) -> list[str]:
        return ["clangd", "-log=verbose", "--background-index"]

    def get_cfg(self, project_path) -> list[str]:
        compile_commands_path = Path(project_path) / "compile_commands.json"
        if compile_commands_path.exists():
            with open(compile_commands_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def on_pre_init(self, project_path):
        compile_commands_path = Path(project_path) / "compile_commands.json"
        if not compile_commands_path.exists():
            log("No compile_commands.json found, creating default one")
            default_config = [
                {
                    "directory": str(Path(project_path).resolve()),
                    "command": "clang++ -std=c++17 -Wall",
                    "file": "main.cpp",
                }
            ]
            with open(compile_commands_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)


class LspEngine:
    def __init__(self, project_path: str, config):
        self.project_path = Path(project_path).resolve()
        self.config = config
        self.opened_files = dict()
        self.diagnostics = dict()
        self.responses = dict()
        self.lsp_client = lsp.Client(
            root_uri=self.project_path.as_uri(), trace="verbose"
        )
        self.config.on_pre_init(str(self.project_path))
        self.runner = ClangdProcess(str(self.project_path), self.lsp_client)
        self._stop_event = threading.Event()
        self._background_thread = None
        self._initialized = False

    def __enter__(self):
        self.runner.__enter__()
        self.initialize_handshake()
        self._initialized = True
        self._background_thread = threading.Thread(
            target=self._background_tick, daemon=True
        )
        self._background_thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop_event.set()
        if self._background_thread and self._background_thread.is_alive():
            self._background_thread.join(timeout=1.0)
        self.runner.__exit__(exc_type, exc_value, traceback)

    def _send(self):
        data_to_send = self.lsp_client.send()
        if data_to_send:
            try:
                self.runner.process.stdin.write(data_to_send)
                self.runner.process.stdin.flush()
            except (IOError, BrokenPipeError) as e:
                log(f"Failed to send to clangd: {e}")

    def _read_and_process(self):
        try:
            data = self.runner.process.stdout.read()
            if data:
                events = self.lsp_client.recv(data)
                for event in events:
                    self.handle_event(event)
        except (IOError, BrokenPipeError):
            pass
        except Exception as e:
            log(f"Error processing data: {e}")

    def _background_tick(self):
        while not self._stop_event.is_set():
            try:
                self._read_and_process()
                time.sleep(0.05)
            except Exception as e:
                log(f"Error in background tick: {e}")

    def wait_for_response(self, msg_id: int, timeout: float = 5.0):
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout:
            if msg_id in self.responses:
                return self.responses.pop(msg_id)
            time.sleep(0.01)
        raise TimeoutError(f"No response for message {msg_id} after {timeout}s")

    def initialize_handshake(self):
        self._send()
        log("Waiting for 'initialize' response...")
        initialized = False
        start_time = time.monotonic()
        while not initialized and time.monotonic() - start_time < 5:
            self._read_and_process()
            if self.lsp_client.state == lsp.ClientState.NORMAL:
                initialized = True
                break
            time.sleep(0.05)
        if not initialized:
            raise RuntimeError("LSP server initialization failed or timed out.")
        self._send()
        log("LSP session initialized successfully.")

    def handle_event(self, event):
        if isinstance(event, lsp.PublishDiagnostics):
            uri = event.uri
            self.diagnostics[uri] = event.diagnostics
            log(f"Received {len(event.diagnostics)} diagnostics for {uri}")
            for diag in event.diagnostics:
                log(f"  - L{diag.range.start.line+1}: {diag.message}")
        elif isinstance(event, lsp.ShowMessage):
            log(f"[Server message {event.type.name}]: {event.message}")
        elif isinstance(event, lsp.LogMessage):
            pass
        elif isinstance(event, lsp.WorkspaceFolders):
            event.reply(
                [
                    lsp.WorkspaceFolder(
                        uri=self.project_path.as_uri(), name=self.project_path.name
                    )
                ]
            )
            self._send()
        elif isinstance(event, lsp.ConfigurationRequest):
            event.reply([{} for _ in event.items])
            self._send()
        elif isinstance(event, lsp.RegisterCapabilityRequest):
            event.reply()
            self._send()
        elif isinstance(event, lsp.WorkDoneProgressCreate):
            event.reply()
            self._send()
        elif isinstance(
            event,
            (
                lsp.WorkDoneProgressBegin,
                lsp.WorkDoneProgressReport,
                lsp.WorkDoneProgressEnd,
            ),
        ):
            pass
        elif isinstance(event, lsp.MethodResponse) and event.message_id is not None:
            self.responses[event.message_id] = event
            log(f"Stored response for message_id {event.message_id}")
        else:
            log(f"Unhandled event of type {type(event).__name__}")


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
                version=1,
                text=str(file),
            )
        )
        self.tick()
        log(f"Opened file: {path_obj}")

    def close_file(self, file_path: str):
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        path = file_path.resolve()
        uri = path.as_uri()
        if uri not in self.engine.opened_files:
            log(f"File {file_path} is not open.")
            return
        del self.engine.opened_files[uri]
        self.engine.lsp_client.did_close(lsp.TextDocumentIdentifier(uri=uri))
        self.tick()
        log(f"Closed file: {file_path}")

    def on_text_change(self, file_path: str, new_content: str):
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        path = file_path.resolve()
        uri = path.as_uri()
        if uri not in self.engine.opened_files:
            log(f"Cannot change text of a file that is not open: {file_path}")
            return
        file_obj = self.engine.opened_files[uri]
        file_obj.contents = new_content.splitlines(True)
        self.engine.lsp_client.did_change(
            text_document=lsp.VersionedTextDocumentIdentifier(uri=uri, version=None),
            content_changes=[
                lsp.TextDocumentContentChangeEvent.whole_document_change(new_content)
            ],
        )
        self.tick()

    def save_file(self, file_path: str):
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        path = file_path.resolve()
        uri = path.as_uri()
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
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        uri = file_path.resolve().as_uri()
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
        except TimeoutError as e:
            log(f"Timeout waiting for completion: {e}")
        return None

    def goto_definition(self, file_path: str, line: int, character: int):
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        uri = file_path.resolve().as_uri()
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
        except TimeoutError as e:
            log(f"Timeout waiting for definition: {e}")
        return None

    def format_document(self, file_path: str):
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        uri = file_path.resolve().as_uri()
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
                self.on_text_change(str(file_path), str(file_obj))
                log(f"Document formatted: {file_path}")
                return True
        except TimeoutError as e:
            log(f"Timeout waiting for formatting: {e}")
        return False

    def get_hover(self, file_path: str, line: int, character: int):
        if not Path(file_path).is_absolute():
            file_path = self.project_path / file_path
        else:
            file_path = Path(file_path)
        uri = file_path.resolve().as_uri()
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
                return response.result
        except TimeoutError as e:
            log(f"Timeout waiting for hover: {e}")
        return None

    def get_diagnostics(self, file_path: str = None):
        if file_path:
            if not Path(file_path).is_absolute():
                file_path = self.project_path / file_path
            else:
                file_path = Path(file_path)
            uri = file_path.resolve().as_uri()
            return self.engine.diagnostics.get(uri, [])
        return self.engine.diagnostics


if __name__ == "__main__":
    project_path = "/home/progamers/cpp_editor/lsp_test_project"
    with LspSession(project_path) as session:
        session.open_file("main.cpp")
        time.sleep(2)
        completions = session.get_completion("main.cpp", line=2, character=10)
        if completions:
            print(f"Found {len(completions.items)} completions")
            for item in completions.items[:10]:
                print(f"  - {item.label}: {item.kind}")
        session.format_document("main.cpp")
        diagnostics = session.get_diagnostics("main.cpp")
        print(f"Found {len(diagnostics)} diagnostics")
        session.close_file("main.cpp")
