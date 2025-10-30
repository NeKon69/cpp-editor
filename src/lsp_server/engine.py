import threading
import time
from pathlib import Path
import sansio_lsp_client as lsp
from src.common.vars import log
from src.lsp_server.process import ClangdProcess


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
        elif isinstance(event, lsp.ResponseError):
            log(f"[Server error] {event.message} (code: {event.code})")
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
