from typing import List
import sansio_lsp_client as lsp
from src.common.vars import log


class OpenedFile:
    def __init__(self, path: str):
        self.path: str = path
        self.contents: List[str] = []
        self.version: int = 1
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.contents = f.readlines()
        except FileNotFoundError:
            with open(path, "w", encoding="utf-8") as f:
                pass
            log(f"Created new file: {path}")
        except (IOError, PermissionError) as e:
            log(f"Error reading file {path}: {e}")
        except Exception as e:
            log(f"An unexpected error occurred while opening {path}: {e}")

    def __str__(self):
        return "".join(self.contents)

    def insert(self, position: lsp.Position, text: str):
        lines_to_insert = text.splitlines(True)
        if not lines_to_insert:
            return
        while position.line >= len(self.contents):
            self.contents.append("\n")
        if self.contents and not self.contents[-1].endswith("\n"):
            self.contents[-1] += "\n"
        original_line = self.contents[position.line]
        original_line_content = original_line.rstrip("\n")
        char_pos = min(position.character, len(original_line_content))
        before_text = original_line_content[:char_pos]
        after_text = original_line_content[char_pos:]
        lines_to_insert[0] = before_text + lines_to_insert[0]
        if not lines_to_insert[-1].endswith("\n"):
            lines_to_insert[-1] += after_text
        else:
            lines_to_insert.append(after_text + "\n")
        self.contents[position.line : position.line + 1] = lines_to_insert

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("".join(self.contents))
            log(f"File saved: {self.path}")
        except (IOError, PermissionError) as e:
            log(f"Error saving file {self.path}: {e}")
