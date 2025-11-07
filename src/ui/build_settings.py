from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QPushButton,
)

from src.configs.build_config import BuildConfig


class BuildSettings(QDialog):
    settings_changed = pyqtSignal(BuildConfig)

    def __init__(self, config: BuildConfig, parent=None):
        super().__init__(parent)

        self._config = config

        self.setWindowTitle("Build Settings")
        self.setGeometry(100, 100, 600, 450)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        compiler_layout = QHBoxLayout()
        compiler_layout.addWidget(QLabel("Compiler:"))
        self._compiler_combo = QComboBox()
        self._compiler_combo.addItems(["gcc", "clang", "msvc"])
        self._compiler_combo.setCurrentText(self._config.compiler)
        compiler_layout.addWidget(self._compiler_combo)
        compiler_layout.addStretch()
        layout.addLayout(compiler_layout)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Config Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["cmake", "custom"])
        self._mode_combo.setCurrentText(self._config.config_mode)
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self._mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        self._cmake_group_label = QLabel("CMake Generator")
        layout.addWidget(self._cmake_group_label)

        self._cmake_generator_combo = QComboBox()
        self._cmake_generator_combo.addItems(
            ["Unix Makefiles", "Visual Studio 16 2019", "MinGW Makefiles", "Ninja"]
        )
        layout.addWidget(self._cmake_generator_combo)

        build_cmd_layout = QHBoxLayout()
        build_cmd_layout.addWidget(QLabel("Build Command:"))
        self._build_cmd_input = QLineEdit()
        self._build_cmd_input.setText(self._config.build_command)
        self._build_cmd_input.setPlaceholderText(
            "cmake -B build && cmake --build build"
        )
        build_cmd_layout.addWidget(self._build_cmd_input)
        layout.addLayout(build_cmd_layout)

        run_cmd_layout = QHBoxLayout()
        run_cmd_layout.addWidget(QLabel("Run Command:"))
        self._run_cmd_input = QLineEdit()
        self._run_cmd_input.setText(self._config.run_command)
        self._run_cmd_input.setPlaceholderText("./build/app")
        run_cmd_layout.addWidget(self._run_cmd_input)
        layout.addLayout(run_cmd_layout)

        layout.addStretch()

        button_layout = QHBoxLayout()

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply_settings)
        button_layout.addWidget(apply_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        self._on_mode_changed(self._config.config_mode)

    def _on_mode_changed(self, mode: str):
        if mode == "cmake":
            self._build_cmd_input.setEnabled(False)
            self._run_cmd_input.setEnabled(False)
            self._cmake_generator_combo.setEnabled(True)
        else:
            self._build_cmd_input.setEnabled(True)
            self._run_cmd_input.setEnabled(True)
            self._cmake_generator_combo.setEnabled(False)

    def _apply_settings(self):
        self._config.compiler = self._compiler_combo.currentText()
        self._config.config_mode = self._mode_combo.currentText()
        self._config.build_command = self._build_cmd_input.text()
        self._config.run_command = self._run_cmd_input.text()
        self._config.save()
        self.settings_changed.emit(self._config)
        self.accept()

    def get_config(self) -> BuildConfig:
        return self._config
