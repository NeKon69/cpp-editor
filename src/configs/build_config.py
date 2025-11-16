from pathlib import Path
from typing import List
import json

from src.common.vars import log
from src.common.project_settings_db import ProjectSettingsDB


class BuildHelper:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.compile_commands_path = project_path / "compile_commands.json"
        self._db = ProjectSettingsDB(project_path)

    def get_build_command(self) -> str:
        return self._db.get_setting(
            "build_command", "cmake -B build && cmake --build build"
        )

    def get_run_command(self) -> str:
        return self._db.get_setting("run_command", "./build/app")

    def set_build_command(self, command: str):
        self._db.set_setting("build_command", command)

    def set_run_command(self, command: str):
        self._db.set_setting("run_command", command)
