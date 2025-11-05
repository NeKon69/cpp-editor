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

    def __init__(
        self, config: Optional[EditorConfig] = None, parent: Optional[QWidget] = None
    ):
        super().__init__(parent)

        self._config = config or EditorConfig()
        self._file_path: Optional[Path] = None
        self._line_number_area = LineNumberArea(self)
        self._highlighter: Optional[PygmentsHighlighter] = None
        self._diagnostics: List[Dict[str, Any]] = []

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

    def keyPressEvent(self, event: QKeyEvent):
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

    def set_file_path(self, path: Path):
        self._file_path = path

    def get_file_path(self) -> Optional[Path]:
        return self._file_path

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
