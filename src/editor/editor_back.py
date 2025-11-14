from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QKeyEvent, QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit, QToolTip

from src.configs.editor_config import EditorConfig
from src.editor.smart_highlighter import SmartHighlighter


class EditorBack:
    """Handles all logic/behavior aspects of the editor."""

    def __init__(self, editor: QPlainTextEdit, config: EditorConfig):
        self._editor = editor
        self._config = config
        self._file_path: Optional[Path] = None
        self._project_path: Optional[Path] = None
        self._highlighter: Optional[SmartHighlighter] = None
        self._diagnostics: List[Dict[str, Any]] = []
        self._skip_next_closing = False

        self._pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}

        self._last_edited_line_with_hash = -1
        self._last_highlighted_content = ""

        self._setup_timers()
        self._setup_signals()

    def _setup_timers(self):
        self._light_highlight_timer = QTimer(self._editor)
        self._light_highlight_timer.setSingleShot(True)
        self._light_highlight_timer.setInterval(1000)
        self._light_highlight_timer.timeout.connect(self._trigger_light_highlight)

        self._heavy_highlight_timer = QTimer(self._editor)
        self._heavy_highlight_timer.setSingleShot(True)
        self._heavy_highlight_timer.setInterval(5000)
        self._heavy_highlight_timer.timeout.connect(self._trigger_heavy_highlight)

    def _setup_signals(self):
        self._editor.textChanged.connect(self._schedule_highlight)

    def _setup_highlighter(self):
        if self._project_path and not self._highlighter:
            self._highlighter = SmartHighlighter(
                self._editor.document(), self._project_path
            )
            self._highlighter.update_colors(self._config.colors)

    def _schedule_highlight(self):
        cursor = self._editor.textCursor()
        current_line = cursor.blockNumber()
        current_line_text = cursor.block().text().lstrip()

        if current_line_text.startswith("#"):
            self._schedule_heavy_highlight(current_line)
        else:
            self._light_highlight_timer.stop()
            self._light_highlight_timer.start()

    def _schedule_heavy_highlight(self, current_line: int):
        if current_line != self._last_edited_line_with_hash:
            self._heavy_highlight_timer.stop()
            self._last_edited_line_with_hash = current_line
            self._heavy_highlight_timer.start()
        else:
            self._heavy_highlight_timer.stop()
            self._heavy_highlight_timer.start()

    def _trigger_light_highlight(self):
        if self._highlighter:
            content = self._editor.toPlainText()

            if content == self._last_highlighted_content:
                return

            self._last_highlighted_content = content
            self._highlighter.update_tree(content, "300ms_edit")

    def _trigger_heavy_highlight(self):
        if self._file_path:
            self.save_file()

        if self._highlighter and self._file_path:
            self._highlighter.preprocess_file(self._file_path, "5s_hash_edit")

    def handle_key_press(self, event: QKeyEvent) -> bool:
        """Returns True if event was handled, False otherwise."""

        if self._handle_semicolon(event):
            return True
        if self._handle_return(event):
            return True
        if self._handle_auto_pair(event):
            return True
        if self._handle_closing_char(event):
            return True
        if self._handle_completion_request(event):
            return True
        if self._handle_quick_fix_request(event):
            return True
        if self._handle_format_request(event):
            return True
        if self._handle_diagnostic_tooltip(event):
            return True

        return False

    def _handle_semicolon(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Semicolon:
            if self._file_path:
                self.save_file()
            return False
        return False

    def _handle_return(self, event: QKeyEvent) -> bool:
        if event.key() != Qt.Key.Key_Return:
            return False

        if self._file_path:
            self.save_file()

        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        indent = self._get_indent_from_line(block_text)

        if block_text.rstrip().endswith(("{", ":")):
            indent += "\t"

        cursor.insertText("\n" + indent)
        self._editor.setTextCursor(cursor)
        return True

    def _handle_auto_pair(self, event: QKeyEvent) -> bool:
        if event.text() not in self._pairs:
            return False

        char = event.text()
        cursor = self._editor.textCursor()

        if not self._should_auto_close(cursor, char):
            return False

        cursor.insertText(char)
        closing = self._pairs[char]
        cursor.insertText(closing)
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        self._editor.setTextCursor(cursor)
        self._skip_next_closing = True
        return True

    def _handle_closing_char(self, event: QKeyEvent) -> bool:
        if event.text() not in self._pairs.values():
            return False

        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        pos = cursor.positionInBlock()

        if self._skip_next_closing and pos < len(block_text):
            if block_text[pos] == event.text():
                cursor.movePosition(
                    QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
                )
                cursor.removeSelectedText()
                self._skip_next_closing = False
                return True

        self._skip_next_closing = False
        return False

    def _handle_completion_request(self, event: QKeyEvent) -> bool:
        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Space
        ):
            cursor = self._editor.textCursor()
            self._editor.completion_requested.emit(
                cursor.blockNumber(), cursor.positionInBlock()
            )
            return True
        return False

    def _handle_quick_fix_request(self, event: QKeyEvent) -> bool:
        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Return
        ):
            cursor = self._editor.textCursor()
            self._editor.quick_fix_requested.emit(
                cursor.blockNumber(), cursor.positionInBlock()
            )
            return True
        return False

    def _handle_format_request(self, event: QKeyEvent) -> bool:
        if (
            event.modifiers()
            == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            and event.key() == Qt.Key.Key_F
        ):
            self._editor.format_requested.emit()
            return True
        return False

    def _handle_diagnostic_tooltip(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_AsciiTilde:
            self._show_current_diagnostic()
            return True
        return False

    def _show_current_diagnostic(self):
        cursor = self._editor.textCursor()
        current_line = cursor.blockNumber()
        diags_on_line = [d for d in self._diagnostics if d["line"] == current_line]

        if diags_on_line:
            messages = [
                f"[{'Error' if d.get('severity', 1) == 1 else 'Warning'}] {d['message']}"
                for d in diags_on_line
            ]
            tooltip_text = "\n\n".join(messages)
            QToolTip.showText(
                self._editor.mapToGlobal(self._editor.cursorRect().bottomLeft()),
                tooltip_text,
                self._editor,
            )

    def _get_indent_from_line(self, text: str) -> str:
        indent = len(text) - len(text.lstrip())
        return text[:indent]

    def _should_auto_close(self, cursor: QTextCursor, char: str) -> bool:
        pos = cursor.positionInBlock()
        block_text = cursor.block().text()

        if pos < len(block_text):
            next_char = block_text[pos]
            if next_char not in (" ", "\t", "\n", ")", "]", "}", ";", ","):
                return False
        return True

    def apply_text_edits(self, edits: List[Dict[str, Any]]):
        if not edits:
            return

        old_cursor = self._editor.textCursor()
        old_block_num = old_cursor.blockNumber()
        old_pos_in_block = old_cursor.positionInBlock()

        cursor = self._editor.textCursor()
        cursor.beginEditBlock()

        self._apply_sorted_edits(cursor, edits)

        cursor.endEditBlock()
        self._restore_cursor_position(old_block_num, old_pos_in_block)

    def _apply_sorted_edits(self, cursor: QTextCursor, edits: List[Dict[str, Any]]):
        for edit in sorted(
            edits, key=lambda e: (e["line"], e["character"]), reverse=True
        ):
            start_line, start_char = edit["line"], edit["character"]
            end_line, end_char = edit.get("end_line", start_line), edit.get(
                "end_character", start_char
            )
            new_text = edit.get("new_text", "")

            start_block = self._editor.document().findBlockByNumber(start_line)
            end_block = self._editor.document().findBlockByNumber(end_line)

            if not start_block.isValid() or not end_block.isValid():
                continue

            start_pos = start_block.position() + start_char
            end_pos = end_block.position() + end_char

            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(new_text)

    def _restore_cursor_position(self, old_block_num: int, old_pos_in_block: int):
        new_cursor = self._editor.textCursor()
        new_block = self._editor.document().findBlockByNumber(old_block_num)

        if new_block.isValid():
            new_pos = new_block.position() + min(
                old_pos_in_block, len(new_block.text())
            )
            new_cursor.setPosition(new_pos)

        self._editor.setTextCursor(new_cursor)

    def goto_position(self, line: int, character: int):
        cursor = QTextCursor(self._editor.document().findBlockByNumber(line))
        cursor.movePosition(
            QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, character
        )
        self._editor.setTextCursor(cursor)
        self._editor.centerCursor()

    def load_file(self, path: Path) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            self._light_highlight_timer.stop()
            self._heavy_highlight_timer.stop()
            self._last_highlighted_content = content

            self._editor.setPlainText(content)
            self._file_path = path
            self._diagnostics = []
            self._last_edited_line_with_hash = -1

            if self._highlighter and self._file_path:
                self._highlighter.preprocess_file(self._file_path, "file_open")

            return True
        except Exception:
            return False

    def save_file(self, path: Optional[Path] = None) -> bool:
        save_path = path or self._file_path
        try:
            if not save_path:
                return False
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self._editor.toPlainText())
            self._file_path = save_path
            return True
        except Exception:
            return False

    def set_project_path(self, path: Path):
        self._project_path = path
        if not self._highlighter:
            self._setup_highlighter()

    def update_diagnostics(self, diagnostics: List[Dict[str, Any]]):
        self._diagnostics = diagnostics

    def set_colors(self, colors):
        if self._highlighter:
            self._highlighter.update_colors(colors)

    def get_file_path(self) -> Optional[Path]:
        return self._file_path
