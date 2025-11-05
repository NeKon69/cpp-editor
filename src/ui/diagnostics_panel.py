from typing import List, Dict, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel

from src.common.vars import log


class DiagnosticsPanel(QWidget):
    diagnostic_clicked = pyqtSignal(int, int)

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

            icon = "❌" if severity == 1 else "⚠️"
            text = f"{icon} Line {line}: {message}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (diag["line"], diag["character"]))

            self._list.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            line, character = data
            self.diagnostic_clicked.emit(line, character)
