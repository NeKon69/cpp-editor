import sqlite3
import os
import sys
from pathlib import Path
from typing import List, Optional

from src.configs.editor_config import EditorColors


class ColorDatabase:
    def __init__(self):
        self.db_path = self._get_db_path()
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()

    def _get_db_path(self) -> Path:
        if sys.platform.startswith("win"):
            base_dir = Path(
                os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")
            )
            appdir = base_dir / "CppEditor"
        else:
            base_dir = Path(
                os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")
            )
            appdir = base_dir / "cpp_editor"
        appdir.mkdir(parents=True, exist_ok=True)
        return appdir / "themes.sqlite"

    def _create_table(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS themes (
                    name TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )

    def get_all_themes(self) -> List[str]:
        cursor = self.conn.execute("SELECT name FROM themes ORDER BY name ASC")
        return [row[0] for row in cursor.fetchall()]

    def load_theme(self, name: str) -> Optional[dict]:
        cursor = self.conn.execute("SELECT data FROM themes WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return None
        import json

        try:
            data = json.loads(row[0])
            return data
        except Exception:
            return None

    def save_theme(self, name: str, colors_dict: dict):
        import json

        data_json = json.dumps(colors_dict)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO themes (name, data) VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET data=excluded.data
                """,
                (name, data_json),
            )

    def delete_theme(self, name: str):
        with self.conn:
            self.conn.execute("DELETE FROM themes WHERE name = ?", (name,))
