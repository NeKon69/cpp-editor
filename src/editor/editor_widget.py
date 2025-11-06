from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QTextFormat,
    QFont,
    QTextCursor,
    QKeyEvent,
    QTextCharFormat,
)
from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit, QToolTip

from src.common.vars import log
from src.editor.highlighter import PygmentsHighlighter
from src.configs.editor_config import EditorConfig, EditorColors


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor._line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor._paint_line_numbers(event)


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
        self._file_path: Optional[Path] = None
        self._project_path: Optional[Path] = None
        self._line_number_area = LineNumberArea(self)
        self._highlighter: Optional[PygmentsHighlighter] = None
        self._diagnostics: List[Dict[str, Any]] = []
        self._auto_format_enabled = True
        self._skip_next_closing = False

        self._pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}

        self._setup_editor()
        self._setup_signals()
        self._setup_highlighter()

    def _setup_editor(self):
        font = QFont(self._config.font_family, self._config.font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * self._config.tab_width
        )
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self._apply_colors()

    def _apply_colors(self):
        palette = self.palette()
        palette.setColor(palette.ColorRole.Base, QColor(self._config.colors.background))
        palette.setColor(palette.ColorRole.Text, QColor(self._config.colors.foreground))
        self.setPalette(palette)

    def _setup_signals(self):
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.textChanged.connect(self._on_text_changed)

        self._update_line_number_area_width(0)

    def _setup_highlighter(self):
        self._highlighter = PygmentsHighlighter(
            self.document(), "cpp", self._config.style_name
        )

    def _get_indent_from_line(self, text: str) -> str:
        indent = len(text) - len(text.lstrip())
        return text[:indent]

    def _should_auto_close(self, cursor: QTextCursor, char: str) -> bool:
        pos = cursor.positionInBlock()
        block = cursor.block()
        block_text = block.text()

        if pos < len(block_text):
            next_char = block_text[pos]
            if next_char not in (" ", "\t", "", "\n"):
                return False

        return True

    def _find_clang_format_config(self) -> Optional[Path]:
        if not self._project_path:
            return None

        config_path = self._project_path / ".clang-format"
        if config_path.exists():
            return config_path

        return None

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Return:
            cursor = self.textCursor()
            block = cursor.block()
            block_text = block.text()

            indent = self._get_indent_from_line(block_text)

            if block_text.rstrip().endswith(("{", ":")):
                indent += "\t"

            super().keyPressEvent(event)

            cursor = self.textCursor()
            cursor.insertText(indent)
            self.setTextCursor(cursor)

            return

        if event.text() in self._pairs:
            char = event.text()
            cursor = self.textCursor()

            if self._should_auto_close(cursor, char):
                super().keyPressEvent(event)

                closing = self._pairs[char]
                cursor = self.textCursor()
                cursor.insertText(closing)
                cursor.movePosition(QTextCursor.MoveOperation.Left)
                self.setTextCursor(cursor)
                self._skip_next_closing = True
                return

        if event.text() in self._pairs.values():
            cursor = self.textCursor()
            block = cursor.block()
            block_text = block.text()
            pos = cursor.positionInBlock()

            if self._skip_next_closing and pos < len(block_text):
                if block_text[pos] == event.text():
                    super().keyPressEvent(event)
                    self._skip_next_closing = False
                    return

            self._skip_next_closing = False

        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Space
        ):
            cursor = self.textCursor()
            line = cursor.blockNumber()
            character = cursor.columnNumber()
            self.completion_requested.emit(line, character)
            return

        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Return
        ):
            cursor = self.textCursor()
            line = cursor.blockNumber()
            character = cursor.columnNumber()
            self.quick_fix_requested.emit(line, character)
            return

        if (
            event.modifiers()
            == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            and event.key() == Qt.Key.Key_F
        ):
            self.format_requested.emit()
            return

        if event.key() == Qt.Key.Key_AsciiTilde:
            self._show_current_diagnostic()
            return

        super().keyPressEvent(event)

    def _show_current_diagnostic(self):
        cursor = self.textCursor()
        current_line = cursor.blockNumber()

        diags_on_line = [d for d in self._diagnostics if d["line"] == current_line]

        if diags_on_line:
            messages = []
            for diag in diags_on_line:
                severity = "Error" if diag.get("severity", 1) == 1 else "Warning"
                messages.append(f"[{severity}] {diag['message']}")

            tooltip_text = "\n\n".join(messages)
            QToolTip.showText(
                self.mapToGlobal(self.cursorRect().bottomLeft()), tooltip_text, self
            )

    def _line_number_area_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _update_line_number_area_width(self, _):
        self.setViewportMargins(self._line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def _paint_line_numbers(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(self._config.colors.line_numbers_bg))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)

                has_error = any(
                    d["line"] == block_number
                    for d in self._diagnostics
                    if d.get("severity", 1) == 1
                )

                if has_error:
                    painter.setPen(QColor("#f92672"))
                else:
                    painter.setPen(QColor(self._config.colors.line_numbers_fg))

                painter.drawText(
                    0,
                    top,
                    self._line_number_area.width() - 3,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )

            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

    def _on_cursor_position_changed(self):
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        column = cursor.columnNumber() + 1
        self.cursor_position_changed.emit(line, column)

        self._highlight_current_line()

    def _on_text_changed(self):
        if self._file_path:
            self.text_changed.emit(self.toPlainText())

    def _highlight_current_line(self):
        extra_selections = []

        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(self._config.colors.current_line)
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)

        for diagnostic in self._diagnostics:
            line = diagnostic["line"]
            character = diagnostic["character"]

            cursor = QTextCursor(self.document().findBlockByNumber(line))
            cursor.movePosition(
                QTextCursor.MoveOperation.Right,
                QTextCursor.MoveMode.MoveAnchor,
                character,
            )
            cursor.movePosition(
                QTextCursor.MoveOperation.EndOfWord, QTextCursor.MoveMode.KeepAnchor
            )

            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor

            fmt = QTextCharFormat()
            if diagnostic.get("severity", 1) == 1:
                fmt.setUnderlineColor(QColor("#f92672"))
            else:
                fmt.setUnderlineColor(QColor("#fd971f"))
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.WaveUnderline)
            selection.format = fmt

            extra_selections.append(selection)

        self.setExtraSelections(extra_selections)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self._line_number_area_width(), cr.height())
        )

    def update_diagnostics(self, diagnostics: List[Dict[str, Any]]):
        self._diagnostics = diagnostics
        self._highlight_current_line()
        self._line_number_area.update()

    def apply_text_edits(self, edits: List[Dict[str, Any]]):
        if not edits:
            return

        old_cursor = self.textCursor()
        old_block = old_cursor.blockNumber()
        old_pos_in_block = old_cursor.positionInBlock()

        cursor = self.textCursor()
        cursor.beginEditBlock()

        for edit in sorted(
            edits, key=lambda e: (e["line"], e["character"]), reverse=True
        ):
            start_line = edit["line"]
            start_char = edit["character"]
            end_line = edit.get("end_line", start_line)
            end_char = edit.get("end_character", start_char)
            new_text = edit.get("new_text", "")

            start_block = self.document().findBlockByNumber(start_line)
            if not start_block.isValid():
                continue

            start_pos = start_block.position() + start_char

            end_block = self.document().findBlockByNumber(end_line)
            if not end_block.isValid():
                continue

            end_pos = end_block.position() + end_char

            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(new_text)

        cursor.endEditBlock()

        new_cursor = self.textCursor()
        new_block = self.document().findBlockByNumber(old_block)
        if new_block.isValid():
            new_pos = new_block.position() + min(
                old_pos_in_block, len(new_block.text())
            )
            new_cursor.setPosition(new_pos)
        self.setTextCursor(new_cursor)

    def goto_position(self, line: int, character: int):
        cursor = QTextCursor(self.document().findBlockByNumber(line))
        cursor.movePosition(
            QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, character
        )
        self.setTextCursor(cursor)
        self.centerCursor()

    def set_colors(self, colors: EditorColors):
        self._config.colors = colors
        self._apply_colors()
        self._highlight_current_line()
        self._line_number_area.update()

    def set_style(self, style_name: str):
        self._config.style_name = style_name
        if self._highlighter:
            self._highlighter.set_style(style_name)

    def set_auto_format_enabled(self, enabled: bool):
        self._auto_format_enabled = enabled

    def set_file_path(self, path: Path):
        self._file_path = path

    def set_project_path(self, path: Path):
        self._project_path = path

    def get_file_path(self) -> Optional[Path]:
        return self._file_path

    def get_clang_format_config(self) -> Optional[Path]:
        return self._find_clang_format_config()

    def load_file(self, path: Path) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            self.setPlainText(content)
            self._file_path = path
            self._diagnostics = []

            log(f"loaded file: {path}")
            return True

        except Exception as e:
            log(f"failed to load file {path}: {e}")
            return False

    def save_file(self, path: Optional[Path] = None) -> bool:
        try:
            save_path = path or self._file_path

            if not save_path:
                return False

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())

            self._file_path = save_path

            log(f"saved file: {save_path}")
            return True

        except Exception as e:
            log(f"failed to save file {save_path}: {e}")
            return False
