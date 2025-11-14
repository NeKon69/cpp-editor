from typing import Optional

from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QColor, QPainter, QTextCharFormat, QTextFormat
from PyQt6.QtWidgets import QWidget, QTextEdit, QPlainTextEdit

from src.configs.editor_config import EditorConfig, EditorColors


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor._editor)
        self._editor = editor

    def sizeHint(self):
        return QSize(self._editor._line_number_area_width(), 0)

    def paintEvent(self, event):
        self._editor._paint_line_numbers(event)


class EditorFront:

    def __init__(self, editor: QPlainTextEdit, config: EditorConfig):
        self._editor = editor
        self._config = config
        self._line_number_area = LineNumberArea(self)
        self._diagnostics = []

        self._setup_visual()
        self._setup_signals()

    def _setup_visual(self):
        from PyQt6.QtGui import QFont

        font = QFont(self._config.font_family, self._config.font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._editor.setFont(font)

        self._editor.setTabStopDistance(
            self._editor.fontMetrics().horizontalAdvance(" ") * self._config.tab_width
        )
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._apply_colors()

    def _setup_signals(self):
        self._editor.blockCountChanged.connect(self._update_line_number_area_width)
        self._editor.updateRequest.connect(self._update_line_number_area)
        self._editor.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_number_area_width(0)

    def _apply_colors(self):
        palette = self._editor.palette()
        palette.setColor(palette.ColorRole.Base, QColor(self._config.colors.background))
        palette.setColor(palette.ColorRole.Text, QColor(self._config.colors.foreground))
        self._editor.setPalette(palette)

    def _line_number_area_width(self) -> int:
        digits = len(str(max(1, self._editor.blockCount())))
        space = 3 + self._editor.fontMetrics().horizontalAdvance("9") * digits
        return space

    def _update_line_number_area_width(self, _):
        self._editor.setViewportMargins(self._line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int):
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )

        if rect.contains(self._editor.viewport().rect()):
            self._update_line_number_area_width(0)

    def _paint_line_numbers(self, event):
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(self._config.colors.line_numbers_bg))

        block = self._editor.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self._editor.blockBoundingGeometry(block)
            .translated(self._editor.contentOffset())
            .top()
        )
        bottom = top + int(self._editor.blockBoundingRect(block).height())

        self._paint_line_numbers_loop(painter, event, block, block_number, top, bottom)

    def _paint_line_numbers_loop(
        self, painter, event, block, block_number, top, bottom
    ):
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
                    self._editor.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + int(self._editor.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self):
        extra_selections = []

        if not self._editor.isReadOnly():
            extra_selections.append(self._create_line_selection())

        extra_selections.extend(self._create_diagnostic_selections())
        self._editor.setExtraSelections(extra_selections)

    def _create_line_selection(self):
        from PyQt6.QtGui import QTextCursor

        selection = QTextEdit.ExtraSelection()
        line_color = QColor(self._config.colors.current_line)
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.cursor = self._editor.textCursor()
        selection.cursor.clearSelection()
        return selection

    def _create_diagnostic_selections(self):
        from PyQt6.QtGui import QTextCursor

        selections = []
        for diagnostic in self._diagnostics:
            line, character = diagnostic["line"], diagnostic["character"]
            cursor = QTextCursor(self._editor.document().findBlockByNumber(line))
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
            selections.append(selection)

        return selections

    def handle_resize(self, event):
        cr = self._editor.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self._line_number_area_width(), cr.height())
        )

    def update_diagnostics(self, diagnostics):
        self._diagnostics = diagnostics
        self._highlight_current_line()
        self._line_number_area.update()

    def set_colors(self, colors: EditorColors):
        self._config.colors = colors
        self._apply_colors()
        self._highlight_current_line()
        self._line_number_area.update()

    def get_line_number_area(self):
        return self._line_number_area
