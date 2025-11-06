import sqlite3
from pathlib import Path
from typing import Optional, Dict
import sys

from src.common.vars import log


class ColorDatabase:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            if getattr(sys, "frozen", False):
                exe_dir = Path(sys.executable).parent
            else:
                exe_dir = Path.cwd()

            self.db_path = exe_dir / ".cpp_editor_colors.db"
        else:
            self.db_path = db_path

        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS color_themes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        keyword TEXT,
                        string TEXT,
                        comment TEXT,
                        function TEXT,
                        type_ TEXT,
                        number TEXT,
                        operator TEXT,
                        foreground TEXT,
                        background TEXT,
                        current_line TEXT,
                        line_numbers_bg TEXT,
                        line_numbers_fg TEXT,
                        selection TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )
                conn.commit()
        except Exception as e:
            log(f"database init error: {e}")

    def save_theme(self, name: str, colors: Dict[str, str]):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO color_themes 
                    (name, keyword, string, comment, function, type_, number, operator, 
                     foreground, background, current_line, line_numbers_bg, line_numbers_fg, selection)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        name,
                        colors.get("keyword"),
                        colors.get("string"),
                        colors.get("comment"),
                        colors.get("function"),
                        colors.get("type_"),
                        colors.get("number"),
                        colors.get("operator"),
                        colors.get("foreground"),
                        colors.get("background"),
                        colors.get("current_line"),
                        colors.get("line_numbers_bg"),
                        colors.get("line_numbers_fg"),
                        colors.get("selection"),
                    ),
                )
                conn.commit()
            log(f"theme saved: {name}")
        except Exception as e:
            log(f"failed to save theme: {e}")

    def load_theme(self, name: str) -> Optional[Dict[str, str]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM color_themes WHERE name = ?", (name,)
                )
                row = cursor.fetchone()

                if row:
                    return {
                        "keyword": row[2],
                        "string": row[3],
                        "comment": row[4],
                        "function": row[5],
                        "type_": row[6],
                        "number": row[7],
                        "operator": row[8],
                        "foreground": row[9],
                        "background": row[10],
                        "current_line": row[11],
                        "line_numbers_bg": row[12],
                        "line_numbers_fg": row[13],
                        "selection": row[14],
                    }
        except Exception as e:
            log(f"failed to load theme: {e}")
        return None

    def get_all_themes(self) -> list:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT name FROM color_themes ORDER BY name")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            log(f"failed to get themes: {e}")
        return []

    def delete_theme(self, name: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM color_themes WHERE name = ?", (name,))
                conn.commit()
            log(f"theme deleted: {name}")
        except Exception as e:
            log(f"failed to delete theme: {e}")
