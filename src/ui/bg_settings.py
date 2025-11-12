from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QCheckBox,
    QPushButton,
)


class BackgroundSettings(QDialog):
    settings_changed = pyqtSignal(bool, int, float)

    def __init__(self, enabled: bool, opacity: int, brightness: float, parent=None):
        super().__init__(parent)

        self._enabled = enabled
        self._opacity = opacity
        self._brightness = brightness

        self.setWindowTitle("Background Settings")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        self._enable_checkbox = QCheckBox("Enable Shader Background")
        self._enable_checkbox.setChecked(enabled)
        self._enable_checkbox.stateChanged.connect(self._on_enable_changed)
        layout.addWidget(self._enable_checkbox)

        layout.addSpacing(10)

        opacity_label = QLabel("Widget Opacity:")
        layout.addWidget(opacity_label)

        opacity_slider_layout = QHBoxLayout()

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setMinimum(100)
        self._opacity_slider.setMaximum(255)
        self._opacity_slider.setValue(opacity)
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_slider_layout.addWidget(self._opacity_slider)

        self._opacity_value_label = QLabel(str(opacity))
        self._opacity_value_label.setMinimumWidth(40)
        opacity_slider_layout.addWidget(self._opacity_value_label)

        layout.addLayout(opacity_slider_layout)

        layout.addSpacing(10)

        brightness_label = QLabel("Shader Brightness:")
        layout.addWidget(brightness_label)

        brightness_slider_layout = QHBoxLayout()

        self._brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self._brightness_slider.setMinimum(10)
        self._brightness_slider.setMaximum(200)
        self._brightness_slider.setValue(int(brightness * 100))
        self._brightness_slider.valueChanged.connect(self._on_brightness_changed)
        brightness_slider_layout.addWidget(self._brightness_slider)

        self._brightness_value_label = QLabel(f"{brightness:.2f}")
        self._brightness_value_label.setMinimumWidth(40)
        brightness_slider_layout.addWidget(self._brightness_value_label)

        layout.addLayout(brightness_slider_layout)

        layout.addSpacing(20)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._apply_settings)
        button_layout.addWidget(apply_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self._on_enable_changed(
            Qt.CheckState.Checked.value if enabled else Qt.CheckState.Unchecked.value
        )

    def _on_enable_changed(self, state):
        self._enabled = state == Qt.CheckState.Checked.value
        self._opacity_slider.setEnabled(self._enabled)
        self._brightness_slider.setEnabled(self._enabled)

    def _on_opacity_changed(self, value):
        self._opacity = value
        self._opacity_value_label.setText(str(value))

    def _on_brightness_changed(self, value):
        self._brightness = value / 100.0
        self._brightness_value_label.setText(f"{self._brightness:.2f}")

    def _apply_settings(self):
        self.settings_changed.emit(self._enabled, self._opacity, self._brightness)
