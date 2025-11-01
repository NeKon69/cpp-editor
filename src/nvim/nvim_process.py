import threading
import pynvim as nvim
from typing import Callable, List, Dict, Any, Optional
from src.common.vars import log


class NvimProcess:
    def __init__(self, nvim_argv: Optional[list[str]] = None):
        if nvim_argv is None:
            self.nvim_argv = ["nvim", "--embed", "--headless", "--clean"]
        else:
            self.nvim_argv = nvim_argv

        self.nvim: Optional[nvim.Nvim] = None
        self._event_thread: Optional[threading.Thread] = None
        self._request_handler: Optional[Callable] = None
        self._notification_handler: Optional[Callable] = None

    def start(self, request_handler: Callable, notification_handler: Callable):
        if self.nvim:
            log("Nvim is already started")
        self.nvim = nvim.attach("child", argv=self.nvim_argv)
        self._request_handler = request_handler
        self._notification_handler = notification_handler
        self._event_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._event_thread.start()
        log(f"Nvim started with process ID: {self.get_pid()}")

    def stop(self):
        if not self.nvim:
            return
        try:
            self.nvim.command("qa!")
        except (nvim.NvimError, IOError, BrokenPipeError) as e:
            log(f"Error stopping nvim: {e}")
        if self._event_thread and self._event_thread.is_alive():
            self._event_thread.join(timeout=2)
        self.nvim = None

    def get_pid(self):
        if self.nvim:
            return self.nvim.funcs.getpid()
        return None

    def _run_loop(self):
        if self.nvim:
            try:
                self.nvim.run_loop(self._request_handler, self._notification_handler)
            except Exception as e:
                log(f"Error in nvim run loop: {e}")

    def get(self):
        return self.nvim

    def __enter__(self, *args):
        self.start(*args)
        return self

    def __exit__(self, *args):
        self.stop()
