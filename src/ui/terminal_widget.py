from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QLabel
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor
from PyQt6.QtCore import pyqtSlot


class TerminalWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("Build Output")
        self._label.setStyleSheet("background: #3e3d32; color: #f8f8f2; padding: 5px;")

        self._terminal = QPlainTextEdit()
        self._terminal.setReadOnly(True)
        self._terminal.setStyleSheet(
            """
            QPlainTextEdit {
                background: #1e1e1e;
                color: #00ff00;
                font-family: monospace;
                font-size: 10pt;
            }
        """
        )

        layout.addWidget(self._label)
        layout.addWidget(self._terminal)

    def append_text(self, text: str, error: bool = False):
        cursor = self._terminal.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        if error:
            fmt.setForeground(QColor("#ff0000"))
        else:
            fmt.setForeground(QColor("#00ff00"))

        cursor.setCharFormat(fmt)
        cursor.insertText(text + "\n")
        self._terminal.setTextCursor(cursor)

    def clear(self):
        self._terminal.clear()

    def set_title(self, title: str):
        self._label.setText(title)
