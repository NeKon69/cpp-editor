from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QColorDialog,
    QGridLayout,
    QComboBox,
    QInputDialog,
)
from PyQt6.QtGui import QColor

from src.configs.editor_config import EditorColors
from src.common.color_database import ColorDatabase


class ThemePicker(QDialog):
    colors_changed = pyqtSignal(EditorColors)

    def __init__(self, current_colors: EditorColors, parent=None):
        super().__init__(parent)

        self._colors = EditorColors(**current_colors.to_dict())
        self._color_buttons = {}
        self._db = ColorDatabase()

        self.setWindowTitle("Syntax Highlighting Colors")
        self.setGeometry(100, 100, 600, 450)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(self._db.get_all_themes())
        self._theme_combo.currentTextChanged.connect(self._load_selected_theme)
        theme_layout.addWidget(self._theme_combo)

        save_theme_button = QPushButton("Save Theme")
        save_theme_button.clicked.connect(self._save_theme)
        theme_layout.addWidget(save_theme_button)

        delete_theme_button = QPushButton("Delete Theme")
        delete_theme_button.clicked.connect(self._delete_theme)
        theme_layout.addWidget(delete_theme_button)

        layout.addLayout(theme_layout)

        grid = QGridLayout()

        color_fields = [
            ("keyword", "Keywords"),
            ("string", "Strings"),
            ("comment", "Comments"),
            ("function", "Functions"),
            ("type_", "Types"),
            ("number", "Numbers"),
            ("operator", "Operators"),
            ("foreground", "Foreground"),
            ("background", "Background"),
        ]

        for row, (field, label) in enumerate(color_fields):
            label_widget = QLabel(label)
            button = QPushButton()
            button.setMinimumWidth(100)
            button.setMinimumHeight(30)

            color = getattr(self._colors, field)
            button.setStyleSheet(f"background-color: {color};")
            button.clicked.connect(
                lambda checked, f=field, b=button: self._pick_color(f, b)
            )

            self._color_buttons[field] = (button, color)
            grid.addWidget(label_widget, row, 0)
            grid.addWidget(button, row, 1)

        layout.addLayout(grid)

        button_layout = QHBoxLayout()

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply_colors)
        button_layout.addWidget(apply_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _pick_color(self, field: str, button: QPushButton):
        current_color = QColor(self._color_buttons[field][1])
        color = QColorDialog.getColor(current_color, self, f"Pick color for {field}")

        if color.isValid():
            hex_color = color.name()
            self._color_buttons[field] = (button, hex_color)
            setattr(self._colors, field, hex_color)
            button.setStyleSheet(f"background-color: {hex_color};")

    def _save_theme(self):
        name, ok = QInputDialog.getText(self, "Save Theme", "Theme name:")
        if ok and name:
            self._db.save_theme(name, self._colors.to_dict())
            self._theme_combo.addItem(name)
            self._theme_combo.setCurrentText(name)

    def _delete_theme(self):
        name = self._theme_combo.currentText()
        if name:
            self._db.delete_theme(name)
            self._theme_combo.removeItem(self._theme_combo.currentIndex())

    def _load_selected_theme(self, name: str):
        if not name:
            return

        theme_data = self._db.load_theme(name)
        if theme_data:
            self._colors = EditorColors.from_dict(theme_data)
            self._update_buttons()

    def _update_buttons(self):
        for field, (button, _) in self._color_buttons.items():
            color = getattr(self._colors, field)
            self._color_buttons[field] = (button, color)
            button.setStyleSheet(f"background-color: {color};")

    def _apply_colors(self):
        self.colors_changed.emit(self._colors)
        self.accept()

    def get_colors(self) -> EditorColors:
        return self._colors
