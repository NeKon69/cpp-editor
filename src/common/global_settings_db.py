import sqlite3
import os
import sys
from pathlib import Path
from typing import List, Optional
import json


class GlobalSettingsDB:
    def __init__(self):
        self.db_path = self._get_db_path()
        self.conn = sqlite3.connect(self.db_path)
        self._create_tables()

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
        return appdir / "global_settings.sqlite"

    def _create_tables(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS themes (
                    name TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
            )
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS global_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
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
        try:
            data = json.loads(row[0])
            return data
        except Exception:
            return None

    def save_theme(self, name: str, colors_dict: dict):
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

    def get_setting(self, key: str) -> Optional[str]:
        cursor = self.conn.execute(
            "SELECT value FROM global_settings WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str):
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO global_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    def delete_setting(self, key: str):
        with self.conn:
            self.conn.execute("DELETE FROM global_settings WHERE key = ?", (key,))
