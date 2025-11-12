import shutil
import subprocess
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal
from src.common.vars import log


def find_executable(name: str) -> Optional[str]:
    return shutil.which(name)


class ProcessRunner(QThread):
    output = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal(int)

    def __init__(self, command: str, cwd: Path = None):
        super().__init__()
        self.command = command
        self.cwd = cwd or Path.cwd()
        self.process = None

    def run(self):
        try:
            self.output.emit(f"$ {self.command}\n")

            self.process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=self.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in self.process.stdout:
                self.output.emit(line)

            self.process.wait()
            self.finished.emit(self.process.returncode)

        except Exception as e:
            log(f"process runner error: {e}")
            self.error.emit(str(e))
            self.finished.emit(-1)

    def stop(self):
        if self.process:
            self.process.terminate()
