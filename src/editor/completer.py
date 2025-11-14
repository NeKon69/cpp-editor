from typing import List, Dict, Any, Tuple
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem
from PyQt6.QtGui import QTextCursor, QFont, QKeyEvent
from src.common.vars import log
import time


class LspCompleter(QWidget):
    def __init__(self, editor):
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )

        self._editor = editor
        self._completions: List[Dict[str, Any]] = []
        self._filtered: List[Dict[str, Any]] = []
        self._last_text_length = 0

        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setFont(QFont("monospace", 10))
        self._list.setStyleSheet(
            """
            QListWidget {
                background-color: #2d2d2d;
                color: #f8f8f2;
                border: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #44475a;
            }
        """
        )
        self._list.itemClicked.connect(self._apply_completion)

        layout.addWidget(self._list)

        self.setFixedWidth(350)
        self.setMaximumHeight(250)

        self._auto_timer = QTimer()
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(300)
        self._auto_timer.timeout.connect(self._auto_request)

        self._editor.textChanged.connect(self._on_text_changed)
        self._editor.installEventFilter(self)

        self.hide()

    def _extract_prefix(self) -> Tuple[str, str]:
        cursor = self._editor.textCursor()
        block = cursor.block().text()
        pos = cursor.positionInBlock()
        i = pos - 1
        while i >= 0:
            c = block[i]
            if c.isalnum() or c == "_":
                i -= 1
            elif i > 0 and block[i - 1 : i + 1] in ("->", "::"):
                i -= 2
            else:
                break
        full_prefix = block[i + 1 : pos]

        if "::" in full_prefix:
            filter_prefix = full_prefix.split("::")[-1]
        elif "->" in full_prefix:
            filter_prefix = full_prefix.split("->")[-1]
        else:
            filter_prefix = full_prefix

        return full_prefix, filter_prefix

    def eventFilter(self, obj, event):
        if obj == self._editor and event.type() == event.Type.KeyPress:
            if self.isVisible():
                key = event.key()

                if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    self._list.keyPressEvent(event)
                    return True
                elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    current = self._list.currentItem()
                    if current:
                        self._apply_completion(current)
                    return True
                elif key == Qt.Key.Key_Escape:
                    self.hide()
                    return True
                elif key in (
                    Qt.Key.Key_Space,
                    Qt.Key.Key_Semicolon,
                    Qt.Key.Key_ParenLeft,
                    Qt.Key.Key_ParenRight,
                    Qt.Key.Key_BracketLeft,
                    Qt.Key.Key_BracketRight,
                    Qt.Key.Key_BraceLeft,
                    Qt.Key.Key_BraceRight,
                    Qt.Key.Key_Comma,
                    Qt.Key.Key_Period,
                    Qt.Key.Key_Less,
                    Qt.Key.Key_Greater,
                ):
                    self.hide()
                    return False

        return super().eventFilter(obj, event)

    def _on_text_changed(self):
        self._auto_timer.stop()

        current_length = len(self._editor.toPlainText())
        text_added = current_length > self._last_text_length
        self._last_text_length = current_length

        cursor = self._editor.textCursor()
        block = cursor.block().text()
        pos = cursor.positionInBlock()

        if pos > 0:
            last_char = block[pos - 1]
            if last_char in " ;,()[]{}.<>\n\t":
                if self.isVisible():
                    self.hide()
                return

        if self.isVisible():
            if text_added:
                self._auto_timer.start()
            else:
                if self._completions:
                    self._filter_and_show()
        elif text_added and pos > 0 and block[:pos].strip():
            self._auto_timer.start()

    def _filter_and_show(self):
        full_prefix, filter_prefix = self._extract_prefix()

        if not filter_prefix:
            pfx_lower = ""
            start_match = self._completions
            other_match = []
        else:
            pfx_lower = filter_prefix.lower()
            start_match = [
                c
                for c in self._completions
                if self._get_base_name(c["label"]).lower().startswith(pfx_lower)
            ]
            other_match = [
                c
                for c in self._completions
                if pfx_lower in self._get_base_name(c["label"]).lower()
                and c not in start_match
            ]

        self._filtered = sorted(
            start_match, key=lambda x: self._get_base_name(x["label"]).lower()
        ) + sorted(other_match, key=lambda x: self._get_base_name(x["label"]).lower())

        self._list.clear()
        for comp in self._filtered:
            detail = comp.get("detail", "")
            label = comp["label"]
            display = f"{label}  {detail}" if detail else label
            item = QListWidgetItem(display)
            clean_label = self._clean_label(label)
            item.setData(Qt.ItemDataRole.UserRole, clean_label)
            self._list.addItem(item)

        if self._filtered:
            height = min(250, max(50, self._list.count() * 25))
            self.setFixedHeight(height)

            rect = self._editor.cursorRect()
            global_pos = self._editor.mapToGlobal(rect.bottomLeft())

            from PyQt6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
            if screen:
                screen_geom = screen.availableGeometry()

                if global_pos.x() < 0 or global_pos.x() > screen_geom.width() - 350:
                    global_pos.setX(
                        max(0, min(global_pos.x(), screen_geom.width() - 350))
                    )

                if global_pos.y() < 0 or global_pos.y() > screen_geom.height() - height:
                    global_pos.setY(
                        max(0, min(global_pos.y(), screen_geom.height() - height))
                    )

            self.move(global_pos)
            self._list.setCurrentRow(0)

            self.show()
            self.raise_()
        else:
            self.hide()

    def _get_base_name(self, label: str) -> str:
        if "(" in label:
            return label[: label.index("(")]
        return label.strip()

    def _clean_label(self, label: str) -> str:
        label = label.strip()
        if "(" in label and ")" in label:
            base = label[: label.index("(")]
            return base + "()"
        return label

    def _auto_request(self):
        cursor = self._editor.textCursor()
        line = cursor.blockNumber()
        char = cursor.positionInBlock()
        self._editor.completion_requested.emit(line, char)

    def update_completions(self, items: List[Dict[str, Any]]):
        self._completions = items

        if items:
            self._filter_and_show()

    def _apply_completion(self, item: QListWidgetItem):
        label = item.data(Qt.ItemDataRole.UserRole)
        cursor = self._editor.textCursor()

        full_prefix, filter_prefix = self._extract_prefix()

        for _ in range(len(filter_prefix)):
            cursor.deletePreviousChar()

        cursor.insertText(label)

        if label.endswith("()"):
            cursor.movePosition(QTextCursor.MoveOperation.Left)

        self._editor.setTextCursor(cursor)
        self.hide()

    def keyPressEvent(self, event: QKeyEvent):
        self._editor.keyPressEvent(event)
