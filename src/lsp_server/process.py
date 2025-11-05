import subprocess
import threading
import time
import queue
from pathlib import Path
from src.common.vars import log, ClangdNotFoundError
import sansio_lsp_client as lsp


class ClangdProcess:
    def __init__(self, project_path: str, lsp_client=None):
        self.project_path = project_path
        self.process = None
        self.lsp_client = lsp_client
        self._reader_thread = None
        self._stderr_thread = None
        self._stop_reading = threading.Event()
        self.read_queue = queue.Queue()

    def __enter__(self):
        try:
            self.process = subprocess.Popen(
                ["clangd", "-log=verbose", "--background-index"],
                cwd=self.project_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            self._stop_reading.clear()
            self._reader_thread = threading.Thread(
                target=self._read_stdout, daemon=True
            )
            self._reader_thread.start()

            self._stderr_thread = threading.Thread(
                target=self._read_stderr, daemon=True
            )
            self._stderr_thread.start()
        except FileNotFoundError as e:
            raise ClangdNotFoundError() from e
        except Exception as e:
            raise RuntimeError(f"Wasn't able to start clangd: {e}") from e
        return self

    def _read_stdout(self):
        try:
            while not self._stop_reading.is_set():
                try:
                    if self.process.poll() is not None:
                        break

                    data = self.process.stdout.read(4096)
                    if data:
                        self.read_queue.put(("stdout", data))
                    else:
                        time.sleep(0.01)
                except (IOError, OSError):
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.01)
        except Exception as e:
            log(f"Reader thread error: {e}")

    def _read_stderr(self):
        try:
            while not self._stop_reading.is_set():
                try:
                    if self.process.poll() is not None:
                        break

                    data = self.process.stderr.read(4096)
                    if not data:
                        time.sleep(0.01)
                except (IOError, OSError):
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.01)
        except Exception as e:
            log(f"Stderr reader error: {e}")

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop_reading.set()

        if not self.process or self.process.poll() is not None:
            return

        if self.lsp_client:
            try:
                if self.lsp_client.state == lsp.ClientState.NORMAL:
                    self.lsp_client.shutdown()
                    data = self.lsp_client.send()
                    if data:
                        try:
                            self.process.stdin.write(data)
                            self.process.stdin.flush()
                        except (IOError, BrokenPipeError):
                            pass
                    time.sleep(0.1)
                if self.lsp_client.state == lsp.ClientState.SHUTDOWN:
                    self.lsp_client.exit()
                    data = self.lsp_client.send()
                    if data:
                        try:
                            self.process.stdin.write(data)
                            self.process.stdin.flush()
                        except (IOError, BrokenPipeError):
                            pass
                    time.sleep(0.1)
            except (IOError, BrokenPipeError, AssertionError):
                self.process.terminate()

        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)

        if self._stderr_thread and self._stderr_thread.is_alive():
            self._stderr_thread.join(timeout=1.0)

        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
