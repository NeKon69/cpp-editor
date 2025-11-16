from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
)


class BuildConfig(QDialog):
    def __init__(self, build_helper, parent=None):
        super().__init__(parent)
        self._build_helper = build_helper
        self.setWindowTitle("Build Settings")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self._build_cmd_edit = QLineEdit()
        self._build_cmd_edit.setText(self._build_helper.get_build_command())
        form_layout.addRow("Build Command:", self._build_cmd_edit)

        self._run_cmd_edit = QLineEdit()
        self._run_cmd_edit.setText(self._build_helper.get_run_command())
        form_layout.addRow("Run Command:", self._run_cmd_edit)

        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()

        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save)
        button_layout.addWidget(save_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _save(self):
        self._build_helper.set_build_command(self._build_cmd_edit.text())
        self._build_helper.set_run_command(self._run_cmd_edit.text())
        self.accept()
