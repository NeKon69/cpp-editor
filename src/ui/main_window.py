from pathlib import Path

from PyQt6.QtCore import QTimer, QSize
from PyQt6.QtWidgets import QMainWindow, QFileDialog

from src.common.vars import log
from src.configs.build_config import BuildConfig
from src.ui.main_front import MainFront
from src.ui.main_back import MainBack


class MainWindow(QMainWindow):

    def __init__(self, project_path: Path):
        super().__init__()

        self._project_path = project_path

        self._theme_picker = None
        self._bg_settings = None

        self._setup_window()

        self._back = MainBack(project_path, self)
        self._front = MainFront(project_path, self._back.get_editor_config(), self)

        self.setCentralWidget(self._front)

        self._front.setup_menubar(self.menuBar())

        self._connect_signals()

        QTimer.singleShot(100, self._init_completer)

    def _init_completer(self):
        self._back.init_completer(self._front.get_editor())

    def _setup_window(self):
        self.setWindowTitle(f"C++ Editor - {self._project_path.name}")
        self.setGeometry(100, 100, 1600, 900)
        self.setMinimumSize(QSize(800, 600))

    def _connect_signals(self):
        self._connect_front_to_back()
        self._connect_back_to_front()
        self._connect_editor_signals()
        self._connect_ui_actions()

    def _connect_front_to_back(self):
        self._front.file_selected.connect(self._back.on_file_selected)
        self._front.save_requested.connect(self._on_save_requested)
        self._front.format_requested.connect(self._on_format_requested)
        self._front.build_requested.connect(self._on_build_requested)
        self._front.run_requested.connect(self._on_run_requested)

    def _connect_back_to_front(self):
        self._back.diagnostics_updated.connect(self._on_diagnostics_updated)
        self._back.project_changed.connect(self._on_project_changed)

    def _connect_editor_signals(self):
        editor = self._front.get_editor()

        editor.text_changed.connect(self._back.on_text_changed)
        editor.completion_requested.connect(self._back.on_completion_requested)
        editor.format_requested.connect(self._on_format_requested)

    def _connect_ui_actions(self):
        self._front.open_project_requested.connect(self._open_project)
        self._front.theme_picker_requested.connect(self._open_theme_picker)
        self._front.bg_settings_requested.connect(self._open_bg_settings)
        self._front.build_settings_requested.connect(self._open_build_settings)
        self._front.diagnostic_clicked.connect(self._on_diagnostic_clicked)

    def _on_save_requested(self):
        editor = self._front.get_editor()
        if editor.save_file():
            self._back.save_file()

    def _on_format_requested(self):
        edits = self._back.format_document()
        if edits:
            self._front.get_editor().apply_text_edits(edits)

    def _on_build_requested(self):
        self._front.show_terminal()
        build_cmd = self._back.build_project()
        self._front.get_terminal().execute_command(build_cmd)

    def _on_run_requested(self):
        self._front.show_terminal()
        combined_cmd = self._back.run_project()
        self._front.get_terminal().execute_command(combined_cmd)

    def _on_diagnostics_updated(self, diagnostics: list):
        editor = self._front.get_editor()
        diagnostics_panel = self._front.get_diagnostics_panel()

        editor.update_diagnostics(diagnostics)
        diagnostics_panel.update_diagnostics(diagnostics)

    def _on_diagnostic_clicked(self, line: int, character: int):
        self._front.get_editor().goto_position(line, character)

    def _on_project_changed(self, path: Path):
        self._front.set_root_path(path)
        self.setWindowTitle(f"C++ Editor - {path.name}")

    def _open_project(self):
        try:
            directory = QFileDialog.getExistingDirectory(
                self, "Select Project Directory", str(self._project_path)
            )

            if directory:
                self._project_path = Path(directory)
                self._back.change_project(self._project_path)

        except Exception as e:
            log(f"failed to change project: {e}")

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File",
            str(self._project_path),
            "C++ Files (*.cpp *.h *.hpp *.c *.cc *.cxx *.hxx)",
        )

        if file_path:
            self._back.on_file_selected(Path(file_path))

    def _open_theme_picker(self):
        from src.ui.theme_picker import ThemePicker

        if not self._theme_picker:
            editor_config = self._back.get_editor_config()
            global_db = self._back.get_global_db()
            self._theme_picker = ThemePicker(editor_config.colors, global_db, self)
            self._theme_picker.colors_changed.connect(self._on_colors_changed)

        editor_config = self._back.get_editor_config()
        self._theme_picker.set_current_theme(editor_config.active_theme)
        self._theme_picker.show()

    def _on_colors_changed(self, colors, theme_name):
        editor_config = self._back.get_editor_config()
        editor_config.colors = colors
        editor_config.active_theme = theme_name
        global_db = self._back.get_global_db()
        editor_config.save(global_db)
        self._front.update_colors(colors)

    def _open_bg_settings(self):
        from src.ui.bg_settings import BackgroundSettings

        if not self._bg_settings:
            enabled, opacity, brightness = self._front.get_bg_settings()
            self._bg_settings = BackgroundSettings(enabled, opacity, brightness, self)
            self._bg_settings.settings_changed.connect(self._on_bg_settings_changed)
        self._bg_settings.show()

    def _on_bg_settings_changed(self, enabled: bool, opacity: int, brightness: float):
        self._front.update_bg_settings(enabled, opacity, brightness)

    def _open_build_settings(self):
        try:
            build_helper = self._back.get_build_helper()
            settings_dialog = BuildConfig(build_helper, self)
            if settings_dialog.exec():
                pass

        except Exception as e:
            log(f"failed to open build settings: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._front.resize_background(self.width(), self.height())

    def closeEvent(self, event):
        self._back.cleanup()
        event.accept()
