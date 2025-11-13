from pathlib import Path
from typing import List
import json
import sqlite3

from src.common.vars import log


class BuildHelper:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.build_dir = project_path / "build"
        self.compile_commands_path = self.build_dir / "compile_commands.json"
        self.db_path = project_path / ".build_settings.sqlite"
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS build_settings (
                    id INTEGER PRIMARY KEY,
                    build_command TEXT NOT NULL,
                    run_command TEXT NOT NULL
                )
            """
            )

            cursor.execute("SELECT COUNT(*) FROM build_settings")
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO build_settings (id, build_command, run_command) VALUES (1, ?, ?)",
                    ("cmake -B build && cmake --build build", "./build/app"),
                )

            conn.commit()
            conn.close()
        except Exception as e:
            log(f"failed to init build settings db: {e}")

    def get_build_command(self) -> str:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT build_command FROM build_settings WHERE id = 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else "cmake -B build && cmake --build build"
        except Exception as e:
            log(f"failed to load build command: {e}")
            return "cmake -B build && cmake --build build"

    def get_run_command(self) -> str:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT run_command FROM build_settings WHERE id = 1")
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else "./build/app"
        except Exception as e:
            log(f"failed to load run command: {e}")
            return "./build/app"

    def set_build_command(self, command: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE build_settings SET build_command = ? WHERE id = 1", (command,)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log(f"failed to save build command: {e}")

    def set_run_command(self, command: str):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE build_settings SET run_command = ? WHERE id = 1", (command,)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log(f"failed to save run command: {e}")
