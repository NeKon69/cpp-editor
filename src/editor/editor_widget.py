from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QPlainTextEdit, QWidget

from src.configs.editor_config import EditorConfig, EditorColors
from src.editor.editor_front import EditorFront
from src.editor.editor_back import EditorBack


class CodeEditor(QPlainTextEdit):
    text_changed = pyqtSignal(str)
    cursor_position_changed = pyqtSignal(int, int)
    completion_requested = pyqtSignal(int, int)
    quick_fix_requested = pyqtSignal(int, int)
    format_requested = pyqtSignal()

    def __init__(
        self, config: Optional[EditorConfig] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self._config = config or EditorConfig()

        self._front = EditorFront(self, self._config)
        self._back = EditorBack(self, self._config)

        self._setup_signals()

    def _setup_signals(self):
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.textChanged.connect(self._on_text_changed)

    def _on_cursor_position_changed(self):
        cursor = self.textCursor()
        block_num = cursor.blockNumber()
        col_num = cursor.columnNumber()
        self.cursor_position_changed.emit(block_num + 1, col_num + 1)

    def _on_text_changed(self):
        file_path = self._back.get_file_path()
        if file_path:
            content = self.toPlainText()
            self.text_changed.emit(content)

    def keyPressEvent(self, event: QKeyEvent):
        if self._back.handle_key_press(event):
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._front.handle_resize(event)

    def update_diagnostics(self, diagnostics: List[Dict[str, Any]]):
        self._back.update_diagnostics(diagnostics)
        self._front.update_diagnostics(diagnostics)

    def apply_text_edits(self, edits: List[Dict[str, Any]]):
        self._back.apply_text_edits(edits)

    def goto_position(self, line: int, character: int):
        self._back.goto_position(line, character)

    def set_colors(self, colors: EditorColors):
        self._config.colors = colors
        self._front.set_colors(colors)
        self._back.set_colors(colors)

    def set_project_path(self, path: Path):
        self._back.set_project_path(path)

    def load_file(self, path: Path) -> bool:
        return self._back.load_file(path)

    def save_file(self, path: Optional[Path] = None) -> bool:
        return self._back.save_file(path)
