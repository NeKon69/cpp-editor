from pathlib import Path
from typing import Optional, List, Dict, Any

from PyQt6.QtCore import Qt, QRect, QSize, pyqtSignal, QTimer
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
from src.editor.smart_highlighter import SmartHighlighter
from src.configs.editor_config import EditorConfig, EditorColors


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self._editor = editor
        log("line_number_area: initialized")

    def sizeHint(self) -> QSize:
        size = QSize(self._editor._line_number_area_width(), 0)
        log(f"line_number_area: sizeHint called, returning width={size.width()}")
        return size

    def paintEvent(self, event):
        log(f"line_number_area: paintEvent triggered")
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
        log("editor: CodeEditor initializing")

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
        log("editor: light highlight timer created (interval=300ms)")

        self._heavy_highlight_timer = QTimer(self)
        self._heavy_highlight_timer.setSingleShot(True)
        self._heavy_highlight_timer.setInterval(5000)
        self._heavy_highlight_timer.timeout.connect(self._trigger_heavy_highlight)
        log("editor: heavy highlight timer created (interval=5000ms)")

        self._setup_editor()
        self._setup_signals()
        log("editor: CodeEditor initialization complete")

    def _setup_editor(self):
        log("editor: setting up editor configuration")
        font = QFont(self._config.font_family, self._config.font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        log(
            f"editor: font set to {self._config.font_family}, size={self._config.font_size}"
        )

        self.setTabStopDistance(
            self.fontMetrics().horizontalAdvance(" ") * self._config.tab_width
        )
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        log(f"editor: tab width={self._config.tab_width}, wrap mode=NoWrap")

        self._apply_colors()

    def _apply_colors(self):
        log("editor: applying colors from config")
        palette = self.palette()
        palette.setColor(palette.ColorRole.Base, QColor(self._config.colors.background))
        palette.setColor(palette.ColorRole.Text, QColor(self._config.colors.foreground))
        self.setPalette(palette)
        log(
            f"editor: colors applied - bg={self._config.colors.background}, fg={self._config.colors.foreground}"
        )

    def _setup_signals(self):
        log("editor: connecting signals")
        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.textChanged.connect(self._on_text_changed)
        self.textChanged.connect(self._schedule_highlight)
        self._update_line_number_area_width(0)
        log("editor: all signals connected")

    def _setup_highlighter(self):
        log("editor: setting up highlighter")
        if self._project_path and not self._highlighter:
            try:
                self._highlighter = SmartHighlighter(
                    self.document(), self._project_path
                )
                log("editor: highlighter initialized successfully")
            except Exception as e:
                log(f"editor: ERROR - failed to initialize highlighter: {e}")
                raise

    def _get_indent_from_line(self, text: str) -> str:
        indent = len(text) - len(text.lstrip())
        result = text[:indent]
        log(f"editor: calculated indent length={indent}")
        return result

    def _should_auto_close(self, cursor: QTextCursor, char: str) -> bool:
        pos = cursor.positionInBlock()
        block_text = cursor.block().text()

        if pos < len(block_text):
            next_char = block_text[pos]
            if next_char not in (" ", "\t", "\n", ")", "]", "}", ";", ","):
                log(
                    f"editor: auto-close check for '{char}' - skipped (next_char='{next_char}')"
                )
                return False
        log(f"editor: auto-close check for '{char}' - approved")
        return True

    def _schedule_highlight(self):
        log("editor: scheduling highlight update")
        self._light_highlight_timer.stop()
        log("editor: light highlight timer stopped")
        self._heavy_highlight_timer.stop()
        log("editor: heavy highlight timer stopped")

        current_line_text = self.textCursor().block().text().lstrip()
        log(f"editor: current line text (stripped): '{current_line_text}'")

        if current_line_text.startswith("#"):
            log(
                "editor: detected preprocessor directive (line starts with '#') - scheduling HEAVY highlight (5s)"
            )
            self._heavy_highlight_timer.start()
        else:
            log("editor: normal content - scheduling light highlight (300ms)")
            self._light_highlight_timer.start()

    def _trigger_light_highlight(self):
        log("editor: LIGHT highlight triggered by timer")
        if self._highlighter:
            try:
                content = self.toPlainText()
                log(f"editor: calling update_tree with {len(content)} bytes of content")
                self._highlighter.update_tree(content)
                log("editor: update_tree completed successfully")
            except Exception as e:
                log(f"editor: ERROR in light highlight: {e}")

    def _trigger_heavy_highlight(self):
        log("editor: HEAVY highlight triggered by timer")
        if self._highlighter and self._file_path:
            try:
                log(f"editor: calling preprocess_file for {self._file_path.name}")
                self._highlighter.preprocess_file(self._file_path)
                log("editor: preprocess_file completed successfully")
            except Exception as e:
                log(f"editor: ERROR in heavy highlight: {e}")
        else:
            log(
                f"editor: WARNING - cannot trigger heavy highlight: highlighter={self._highlighter is not None}, file_path={self._file_path}"
            )

    def keyPressEvent(self, event: QKeyEvent):
        log(f"editor: keyPressEvent - key={event.key()}, text='{event.text()}'")

        if event.key() == Qt.Key.Key_Return:
            log("editor: Return key pressed")
            cursor = self.textCursor()
            block_text = cursor.block().text()
            indent = self._get_indent_from_line(block_text)

            if block_text.rstrip().endswith(("{", ":")):
                indent += "\t"
                log("editor: adding extra indent after '{' or ':'")

            super().keyPressEvent(event)
            cursor = self.textCursor()
            cursor.insertText(indent)
            self.setTextCursor(cursor)
            return

        if event.text() in self._pairs:
            char = event.text()
            cursor = self.textCursor()
            if self._should_auto_close(cursor, char):
                log(f"editor: auto-closing pair '{char}'")
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
                    log(f"editor: skipping auto-generated closing '{event.text()}'")
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
            log("editor: Ctrl+Space - requesting completion")
            cursor = self.textCursor()
            self.completion_requested.emit(cursor.blockNumber(), cursor.columnNumber())
            return

        if (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Return
        ):
            log("editor: Ctrl+Return - requesting quick fix")
            cursor = self.textCursor()
            self.quick_fix_requested.emit(cursor.blockNumber(), cursor.columnNumber())
            return

        if (
            event.modifiers()
            == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
            and event.key() == Qt.Key.Key_F
        ):
            log("editor: Ctrl+Alt+F - requesting format")
            self.format_requested.emit()
            return

        if event.key() == Qt.Key.Key_AsciiTilde:
            log("editor: Tilde key - showing current diagnostic")
            self._show_current_diagnostic()
            return

        super().keyPressEvent(event)

    def _show_current_diagnostic(self):
        log("editor: showing current diagnostic")
        cursor = self.textCursor()
        current_line = cursor.blockNumber()
        diags_on_line = [d for d in self._diagnostics if d["line"] == current_line]
        log(f"editor: found {len(diags_on_line)} diagnostic(s) on line {current_line}")

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
        log(
            f"editor: line_number_area_width calculated: {space} (digits={digits}, block_count={self.blockCount()})"
        )
        return space

    def _update_line_number_area_width(self, _):
        log("editor: updating line number area width")
        self.setViewportMargins(self._line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect: QRect, dy: int):
        log(f"editor: updating line number area - dy={dy}")
        if dy:
            self._line_number_area.scroll(0, dy)
        else:
            self._line_number_area.update(
                0, rect.y(), self._line_number_area.width(), rect.height()
            )

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width(0)

    def _paint_line_numbers(self, event):
        log(f"editor: painting line numbers - area rect={event.rect()}")
        painter = QPainter(self._line_number_area)
        painter.fillRect(event.rect(), QColor(self._config.colors.line_numbers_bg))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = int(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + int(self.blockBoundingRect(block).height())
        lines_painted = 0

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
                lines_painted += 1
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            block_number += 1

        log(f"editor: painted {lines_painted} line numbers")

    def _on_cursor_position_changed(self):
        cursor = self.textCursor()
        block_num = cursor.blockNumber()
        col_num = cursor.columnNumber()
        log(
            f"editor: cursor position changed - line={block_num + 1}, column={col_num + 1}"
        )
        self.cursor_position_changed.emit(block_num + 1, col_num + 1)
        self._highlight_current_line()

    def _on_text_changed(self):
        if self._file_path:
            content = self.toPlainText()
            log(f"editor: text changed - {len(content)} bytes")
            self.text_changed.emit(content)

    def _highlight_current_line(self):
        log("editor: highlighting current line")
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
        log(f"editor: set {len(extra_selections)} extra selections")

    def resizeEvent(self, event):
        log(f"editor: resizeEvent - new size={event.size()}")
        super().resizeEvent(event)
        cr = self.contentsRect()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self._line_number_area_width(), cr.height())
        )

    def update_diagnostics(self, diagnostics: List[Dict[str, Any]]):
        log(f"editor: updating diagnostics - {len(diagnostics)} diagnostic(s)")
        self._diagnostics = diagnostics
        self._highlight_current_line()
        self._line_number_area.update()

    def apply_text_edits(self, edits: List[Dict[str, Any]]):
        if not edits:
            log("editor: apply_text_edits - no edits to apply")
            return
        log(f"editor: applying {len(edits)} text edit(s)")
        old_cursor = self.textCursor()
        old_block_num = old_cursor.blockNumber()
        old_pos_in_block = old_cursor.positionInBlock()
        cursor = self.textCursor()
        cursor.beginEditBlock()
        for i, edit in enumerate(
            sorted(edits, key=lambda e: (e["line"], e["character"]), reverse=True)
        ):
            start_line, start_char = edit["line"], edit["character"]
            end_line, end_char = edit.get("end_line", start_line), edit.get(
                "end_character", start_char
            )
            new_text = edit.get("new_text", "")
            log(
                f"editor: applying edit {i+1}/{len(edits)} - line {start_line}:{start_char} -> {end_line}:{end_char}, text='{new_text[:20]}...'"
            )
            start_block = self.document().findBlockByNumber(start_line)
            end_block = self.document().findBlockByNumber(end_line)
            if not start_block.isValid() or not end_block.isValid():
                log(f"editor: WARNING - invalid blocks for edit {i+1}")
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
        log("editor: text edits applied successfully")

    def goto_position(self, line: int, character: int):
        log(f"editor: going to position {line}:{character}")
        cursor = QTextCursor(self.document().findBlockByNumber(line))
        cursor.movePosition(
            QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.MoveAnchor, character
        )
        self.setTextCursor(cursor)
        self.centerCursor()

    def set_colors(self, colors: EditorColors):
        log("editor: setting new colors")
        self._config.colors = colors
        self._apply_colors()
        self._highlight_current_line()
        self._line_number_area.update()

    def set_auto_format_enabled(self, enabled: bool):
        log(f"editor: auto-format {'enabled' if enabled else 'disabled'}")
        self._auto_format_enabled = enabled

    def set_file_path(self, path: Path):
        log(f"editor: setting file path to {path}")
        self._file_path = path

    def set_project_path(self, path: Path):
        log(f"editor: setting project path to {path}")
        self._project_path = path
        if not self._highlighter:
            self._setup_highlighter()

    def get_file_path(self) -> Optional[Path]:
        return self._file_path

    def load_file(self, path: Path) -> bool:
        log(f"editor: loading file {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            log(f"editor: file read successfully - {len(content)} bytes")

            self._light_highlight_timer.stop()
            self._heavy_highlight_timer.stop()
            log("editor: both highlight timers stopped")

            self.setPlainText(content)
            self._file_path = path
            self._diagnostics = []
            log("editor: content set, diagnostics cleared")

            if self._highlighter and self._file_path:
                log("editor: triggering initial preprocess_file")
                self._highlighter.preprocess_file(self._file_path)

            log(f"editor: file {path} loaded successfully")
            return True
        except Exception as e:
            log(f"editor: ERROR loading {path}: {e}")
            return False

    def save_file(self, path: Optional[Path] = None) -> bool:
        save_path = path or self._file_path
        log(f"editor: saving file to {save_path}")
        try:
            if not save_path:
                log("editor: ERROR - no save path provided")
                return False

            with open(save_path, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
            log(f"editor: file written successfully")

            self._file_path = save_path

            if self._highlighter:
                log("editor: triggering preprocess_file after save")
                self._highlighter.preprocess_file(save_path)

            log(f"editor: file {save_path} saved successfully")
            return True
        except Exception as e:
            log(f"editor: ERROR saving {save_path}: {e}")
            return False
