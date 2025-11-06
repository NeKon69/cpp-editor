from typing import List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMenu,
)
from PyQt6.QtGui import QColor

from src.common.vars import log


class DiagnosticsPanel(QWidget):
    diagnostic_clicked = pyqtSignal(int, int)
    apply_fix_requested = pyqtSignal(int, int, str)

    def __init__(self):
        super().__init__()

        self._diagnostics: List[Dict[str, Any]] = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._header = QLabel("Diagnostics (0)")
        self._header.setStyleSheet("background: #3e3d32; padding: 5px; color: #f8f8f2;")

        self._list = QListWidget()
        self._list.setStyleSheet(
            """
            QListWidget {
                background: #272822;
                color: #f8f8f2;
                border: none;
            }
            QListWidget::item:selected {
                background: #49483e;
            }
        """
        )
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)

        layout.addWidget(self._header)
        layout.addWidget(self._list)

        self.setMaximumHeight(200)

    def update_diagnostics(self, diagnostics: List[Dict[str, Any]]):
        self._diagnostics = diagnostics
        self._list.clear()

        self._header.setText(f"Diagnostics ({len(diagnostics)})")

        for diag in diagnostics:
            line = diag["line"] + 1
            severity = diag.get("severity", 1)
            message = diag["message"]
            has_fix = "(fix available)" in message

            icon = "❌" if severity == 1 else "⚠️"
            fix_indicator = " 🔧" if has_fix else ""
            text = f"{icon} Line {line}: {message}{fix_indicator}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (diag["line"], diag["character"]))

            if has_fix:
                item.setForeground(QColor("#a6e22e"))

            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            line, character = data
            self.diagnostic_clicked.emit(line, character)

    def _on_context_menu(self, position):
        item = self._list.itemAt(position)
        if not item:
            return

        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return

        line, character = data
        message = item.text()

        if "(fix available)" not in message:
            return

        menu = QMenu(self)
        fix_action = menu.addAction("Apply Fix")
        fix_action.triggered.connect(
            lambda: self.apply_fix_requested.emit(line, character, message)
        )

        menu.exec(self._list.mapToGlobal(position))
