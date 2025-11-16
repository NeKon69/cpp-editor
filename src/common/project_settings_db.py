import sqlite3
from pathlib import Path
from typing import Optional


class ProjectSettingsDB:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.db_path = self._get_db_path()
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()

    def _get_db_path(self) -> Path:
        editor_dir = self.project_path / ".editor"
        editor_dir.mkdir(parents=True, exist_ok=True)
        return editor_dir / "project.sqlite"

    def _create_table(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

    def get_setting(self, key: str, default: str = "") -> str:
        cursor = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str):
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (key, value),
            )

    def delete_setting(self, key: str):
        with self.conn:
            self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))

    def close(self):
        self.conn.close()
