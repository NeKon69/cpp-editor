from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import (
    Qt,
    QTimer,
    pyqtSignal,
    QRect,
)
from PyQt6.QtGui import (
    QFont,
    QKeyEvent,
    QTextCursor,
    QTextCharFormat,
    QColor,
    QTextFormat,
    QPainter,
)
from PyQt6.QtWidgets import (
    QPlainTextEdit,
    QWidget,
    QToolTip,
    QTextEdit,
)

from src.configs.editor_config import EditorColors
from src.editor.smart_highlighter import SmartHighlighter


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self):
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
        self._highlighter: Optional[SmartHighlighter] = None
        self._diagnostics: List[Dict[str, Any]] = []
        self._auto_format_enabled = True
        self._skip_next_closing = False

        self._pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}

        self._light_highlight_timer = QTimer(self)
        self._light_highlight_timer.setSingleShot(True)
        self._light_highlight_timer.setInterval(300)
        self._light_highlight_timer.timeout.connect(self._trigger_light_highlight)

        self._heavy_highlight_timer = QTimer(self)
        self._heavy_highlight_timer.setSingleShot(True)
        self._heavy_highlight_timer.setInterval(5000)
        self._heavy_highlight_timer.timeout.connect(self._trigger_heavy_highlight)

        self._last_edited_line_with_hash = -1
        self._last_highlighted_content = ""

        self._setup_editor()
        self._setup_signals()

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
        self.textChanged.connect(self._schedule_highlight)
        self._update_line_number_area_width(0)

    def _setup_highlighter(self):
        if self._project_path and not self._highlighter:
            self._highlighter = SmartHighlighter(self.document(), self._project_path)
            self._highlighter.update_colors(self._config.colors)

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

    def _schedule_highlight(self):
        cursor = self.textCursor()
        current_line = cursor.blockNumber()
        current_line_text = cursor.block().text().lstrip()

        if current_line_text.startswith("#"):
            if current_line != self._last_edited_line_with_hash:
                self._heavy_highlight_timer.stop()
                self._last_edited_line_with_hash = current_line
                self._heavy_highlight_timer.start()
            else:
                self._heavy_highlight_timer.stop()
                self._heavy_highlight_timer.start()
        else:
            self._light_highlight_timer.stop()
            self._light_highlight_timer.start()

    def _trigger_light_highlight(self):
        if self._highlighter:
            content = self.toPlainText()

            if content == self._last_highlighted_content:
                return

            self._last_highlighted_content = content
            self._highlighter.update_tree(content, "300ms_edit")

    def _trigger_heavy_highlight(self):
        if self._file_path:
            self.save_file()

        if self._highlighter and self._file_path:
            self._highlighter.preprocess_file(self._file_path, "5s_hash_edit")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Semicolon:
            super().keyPressEvent(event)
            if self._file_path:
                self.save_file()
            return

        if event.key() == Qt.Key.Key_Return:
            if self._file_path:
                self.save_file()

            cursor = self.textCursor()
            block_text = cursor.block().text()
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
            block_text = cursor.block().text()
            pos = cursor.positionInBlock()

            if self._skip_next_closing and pos < len(block_text):
                if block_text[pos] == event.text():
                    cursor.movePosition(
                        QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor
                    )
                    cursor.removeSelectedText()
                    self._skip_next_closing = False
                    return
            self._skip_next_closing = False

        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Space
        ):
            cursor = self.textCursor()
            self.completion_requested.emit(cursor.blockNumber(), cursor.columnNumber())
            return

        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Return
        ):
            cursor = self.textCursor()
            self.quick_fix_requested.emit(cursor.blockNumber(), cursor.columnNumber())
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
            messages = [
                f"[{'Error' if d.get('severity', 1) == 1 else 'Warning'}] {d['message']}"
                for d in diags_on_line
            ]
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
                painter.setPen(
                    QColor("#f92672")
                    if has_error
                    else QColor(self._config.colors.line_numbers_fg)
                )
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
        block_num = cursor.blockNumber()
        col_num = cursor.columnNumber()
        self.cursor_position_changed.emit(block_num + 1, col_num + 1)
        self._highlight_current_line()

    def _on_text_changed(self):
        if self._file_path:
            content = self.toPlainText()
            self.text_changed.emit(content)

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
            line, character = diagnostic["line"], diagnostic["character"]
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
            fmt.setUnderlineColor(
                QColor("#f92672")
                if diagnostic.get("severity", 1) == 1
                else QColor("#fd971f")
            )
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
        old_block_num = old_cursor.blockNumber()
        old_pos_in_block = old_cursor.positionInBlock()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for edit in sorted(
            edits, key=lambda e: (e["line"], e["character"]), reverse=True
        ):
            start_line, start_char = edit["line"], edit["character"]
            end_line, end_char = edit.get("end_line", start_line), edit.get(
                "end_character", start_char
            )
            new_text = edit.get("new_text", "")
            start_block = self.document().findBlockByNumber(start_line)
            end_block = self.document().findBlockByNumber(end_line)
            if not start_block.isValid() or not end_block.isValid():
                continue
            start_pos = start_block.position() + start_char
            end_pos = end_block.position() + end_char
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(new_text)
        cursor.endEditBlock()
        new_cursor = self.textCursor()
        new_block = self.document().findBlockByNumber(old_block_num)
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

        if self._highlighter:
            self._highlighter.update_colors(colors)

    def set_project_path(self, path: Path):
        self._project_path = path
        if not self._highlighter:
            self._setup_highlighter()

    def load_file(self, path: Path) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            self._light_highlight_timer.stop()
            self._heavy_highlight_timer.stop()
            self._last_highlighted_content = content

            self.setPlainText(content)
            self._file_path = path
            self._diagnostics = []
            self._last_edited_line_with_hash = -1

            if self._highlighter and self._file_path:
                self._highlighter.preprocess_file(self._file_path, "file_open")

            return True
        except Exception as e:
            return False

    def save_file(self, path: Optional[Path] = None) -> bool:
        save_path = path or self._file_path
        try:
            if not save_path:
                return False
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
            self._file_path = save_path
            return True
        except Exception:
            return False
