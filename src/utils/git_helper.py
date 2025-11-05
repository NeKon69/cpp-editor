import subprocess
from pathlib import Path

from src.common.vars import log


class GitHelper:
    @staticmethod
    def open_lazygit(project_path: Path):
        """Open lazygit in project directory"""
        try:
            subprocess.Popen(
                ["lazygit"],
                cwd=str(project_path),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            log(f"opened lazygit in {project_path}")

        except FileNotFoundError:
            raise RuntimeError("lazygit not found in PATH")

        except Exception as e:
            raise RuntimeError(f"failed to start lazygit: {e}")
