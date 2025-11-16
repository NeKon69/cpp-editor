from PyQt6.QtCore import pyqtSignal
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
    QScrollArea,
    QWidget,
    QMessageBox,
)
from PyQt6.QtGui import QColor

from src.configs.editor_config import EditorColors


class ThemePicker(QDialog):
    colors_changed = pyqtSignal(EditorColors, str)

    def __init__(self, current_colors: EditorColors, global_db, parent=None):
        super().__init__(parent)

        self._colors = EditorColors(**current_colors.to_dict())
        self._color_buttons = {}
        self._db = global_db

        self.setWindowTitle("Theme Editor")
        self.setGeometry(100, 100, 700, 600)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Theme:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(self._db.get_all_themes())
        self._theme_combo.currentTextChanged.connect(self._load_selected_theme)
        theme_layout.addWidget(self._theme_combo, 1)

        new_theme_button = QPushButton("New")
        new_theme_button.clicked.connect(self._new_theme)
        theme_layout.addWidget(new_theme_button)

        save_theme_button = QPushButton("Save")
        save_theme_button.clicked.connect(self._save_theme)
        theme_layout.addWidget(save_theme_button)

        delete_theme_button = QPushButton("Delete")
        delete_theme_button.clicked.connect(self._delete_theme)
        theme_layout.addWidget(delete_theme_button)

        layout.addLayout(theme_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        grid = QGridLayout(scroll_widget)

        color_fields = [
            (
                "Editor",
                [
                    ("background", "Background"),
                    ("foreground", "Foreground"),
                    ("current_line", "Current Line"),
                    ("line_numbers_bg", "Line Numbers BG"),
                    ("line_numbers_fg", "Line Numbers FG"),
                ],
            ),
            (
                "Syntax",
                [
                    ("keyword", "Keywords"),
                    ("type_primitive", "Primitive Types"),
                    ("type_class", "Classes"),
                    ("type_struct", "Structs"),
                    ("type_enum", "Enums"),
                    ("namespace", "Namespaces"),
                    ("function_call", "Function Calls"),
                    ("function_definition", "Function Definitions"),
                    ("member", "Members"),
                    ("variable", "Variables"),
                    ("variable_qualified", "Qualified Variables"),
                    ("variable_builtin", "Built-in Variables"),
                    ("operator", "Operators"),
                    ("string", "Strings"),
                    ("number", "Numbers"),
                    ("comment", "Comments"),
                    ("constant_builtin", "Built-in Constants"),
                    ("preproc", "Preprocessor"),
                ],
            ),
        ]

        row = 0
        for section_name, fields in color_fields:
            section_label = QLabel(f"<b>{section_name}</b>")
            grid.addWidget(section_label, row, 0, 1, 2)
            row += 1

            for field, label in fields:
                label_widget = QLabel(label)
                button = QPushButton()
                button.setMinimumWidth(120)
                button.setMinimumHeight(30)

                color = getattr(self._colors, field)
                button.setStyleSheet(
                    f"background-color: {color}; color: {'#000' if self._is_light_color(color) else '#FFF'};"
                )
                button.setText(color)
                button.clicked.connect(
                    lambda _, f=field, b=button: self._pick_color(f, b)
                )

                self._color_buttons[field] = (button, color)
                grid.addWidget(label_widget, row, 0)
                grid.addWidget(button, row, 1)
                row += 1

        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll, 1)

        button_layout = QHBoxLayout()

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply_colors)
        button_layout.addWidget(apply_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _is_light_color(self, hex_color: str) -> bool:
        try:
            color = QColor(hex_color)
            luminance = (
                0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
            ) / 255
            return luminance > 0.5
        except:
            return False

    def _pick_color(self, field: str, button: QPushButton):
        current_color = QColor(self._color_buttons[field][1])
        color = QColorDialog.getColor(current_color, self, f"Pick color for {field}")

        if color.isValid():
            hex_color = color.name()
            self._color_buttons[field] = (button, hex_color)
            setattr(self._colors, field, hex_color)
            button.setStyleSheet(
                f"background-color: {hex_color}; color: {'#000' if self._is_light_color(hex_color) else '#FFF'};"
            )
            button.setText(hex_color)

    def _new_theme(self):
        name, ok = QInputDialog.getText(self, "New Theme", "Theme name:")
        if ok and name:
            if name in self._db.get_all_themes():
                QMessageBox.warning(self, "Error", "Theme already exists")
                return
            self._db.save_theme(name, self._colors.to_dict())
            self._theme_combo.addItem(name)
            self._theme_combo.setCurrentText(name)

    def _save_theme(self):
        name = self._theme_combo.currentText()
        if name:
            self._db.save_theme(name, self._colors.to_dict())
            QMessageBox.information(self, "Success", f"Theme '{name}' saved")
        else:
            name, ok = QInputDialog.getText(self, "Save Theme", "Theme name:")
            if ok and name:
                self._db.save_theme(name, self._colors.to_dict())
                self._theme_combo.addItem(name)
                self._theme_combo.setCurrentText(name)

    def _delete_theme(self):
        name = self._theme_combo.currentText()
        if not name:
            return

        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Delete theme '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
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
            button.setStyleSheet(
                f"background-color: {color}; color: {'#000' if self._is_light_color(color) else '#FFF'};"
            )
            button.setText(color)

    def _apply_colors(self):
        theme_name = self._theme_combo.currentText()
        self.colors_changed.emit(self._colors, theme_name)
        self.accept()

    def get_colors(self) -> EditorColors:
        return self._colors

    def set_current_theme(self, theme_name: str):
        index = self._theme_combo.findText(theme_name)
        if index >= 0:
            self._theme_combo.setCurrentIndex(index)
