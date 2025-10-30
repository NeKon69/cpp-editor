import subprocess
import os
import time
from src.common.vars import log, ClangdNotFoundError
import sansio_lsp_client as lsp


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
            except (IOError, BrokenPipeError, AssertionError):
                self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
