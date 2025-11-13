from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QFileDialog,
    QStatusBar,
)

from src.common.vars import log
from src.configs.editor_config import EditorConfig
from src.configs.build_config import BuildConfig
from src.editor.editor_widget import CodeEditor
from src.editor.lsp_integration import LspIntegration
from src.editor.completer import LspCompleter
from src.editor.build_helper import BuildHelper
from src.lsp_server.session import LspSession
from src.ui.file_tree import FileTree
from src.ui.diagnostics_panel import DiagnosticsPanel
from src.ui.terminal_widget import TerminalWidget
from src.utils.git_helper import GitHelper


class MainWindow(QMainWindow):

    def __init__(self, project_path: Path):
        super().__init__()

        self._project_path = project_path
        self._current_file: Optional[Path] = None
        self._editor_config = EditorConfig.load()
        self._build_helper = BuildHelper(project_path)

        self._theme_picker = None
        self._bg_settings = None
        self._bg_enabled = True
        self._bg_opacity = 200
        self._bg_brightness = 0.6

        self._setup_window()
        self._setup_lsp()
        self._setup_ui()
        self._setup_menubar()
        self._setup_editor()
        self._setup_statusbar()
        self._setup_timers()
        QTimer.singleShot(100, self._init_completer)

    def _init_completer(self):
        from src.editor.completer import LspCompleter

        self._completer = LspCompleter(self._editor)
        self._lsp_integration.completion_ready.connect(
            self._completer.update_completions
        )

    def _setup_window(self):
        self.setWindowTitle(f"C++ Editor - {self._project_path.name}")
        self.setGeometry(100, 100, 1600, 900)
        self.setMinimumSize(QSize(800, 600))

    def _setup_lsp(self):
        try:
            self._lsp_session = LspSession(str(self._project_path))
            self._lsp_session.__enter__()

            self._lsp_integration = LspIntegration(self._lsp_session)

            log("lsp session initialized")

        except Exception as e:
            log(f"failed to initialize lsp: {e}")

    def _setup_ui(self):
        from src.ui.shader_bg import OpenGLBackground

        central = QWidget()
        self.setCentralWidget(central)

        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self._bg = OpenGLBackground(container)
        self._bg.set_brightness(self._bg_brightness)
        self._bg.setGeometry(0, 0, self.width(), self.height())
        self._bg.lower()

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setHandleWidth(1)
        main_splitter.setStyleSheet("QSplitter { background: transparent; }")

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(1)
        h_splitter.setStyleSheet("QSplitter { background: transparent; }")

        self._file_tree = FileTree(self._project_path)
        self._file_tree.file_selected.connect(self._on_file_selected)
        self._file_tree.setMinimumWidth(200)
        self._file_tree.setMaximumWidth(400)
        self._update_widget_style(self._file_tree)

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(1)
        v_splitter.setStyleSheet("QSplitter { background: transparent; }")

        self._editor = CodeEditor(self._editor_config)
        self._editor.set_project_path(self._project_path)
        self._editor.set_colors(self._editor_config.colors)
        self._update_widget_style(self._editor, is_editor=True)

        self._diagnostics_panel = DiagnosticsPanel()
        self._diagnostics_panel.diagnostic_clicked.connect(self._on_diagnostic_clicked)
        self._diagnostics_panel.hide()
        self._update_widget_style(self._diagnostics_panel, bg_color="40, 40, 40")

        v_splitter.addWidget(self._editor)
        v_splitter.addWidget(self._diagnostics_panel)
        v_splitter.setStretchFactor(0, 1)
        v_splitter.setStretchFactor(1, 0)

        h_splitter.addWidget(self._file_tree)
        h_splitter.addWidget(v_splitter)
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)

        self._terminal = TerminalWidget()
        self._terminal.set_working_dir(self._project_path)
        self._terminal.setMaximumHeight(1000)
        self._terminal.hide()
        self._update_widget_style(self._terminal)

        main_splitter.addWidget(h_splitter)
        main_splitter.addWidget(self._terminal)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 0)

        main_layout.addWidget(main_splitter)

        overlay_widget = QWidget(container)
        overlay_widget.setLayout(main_layout)
        overlay_widget.setStyleSheet("background: transparent;")
        overlay_widget.setGeometry(0, 0, self.width(), self.height())
        overlay_widget.raise_()

        self._overlay = overlay_widget

        central_layout.addWidget(container)

    def _update_widget_style(self, widget, bg_color="30, 30, 30", is_editor=False):
        if self._bg_enabled:
            if is_editor:
                widget.setStyleSheet(
                    f"""
                    QPlainTextEdit {{
                        background-color: rgba({bg_color}, {self._bg_opacity});
                        border: none;
                    }}
                """
                )
            else:
                widget.setStyleSheet(
                    f"""
                    QTreeView {{
                        background-color: rgba({bg_color}, {self._bg_opacity});
                        color: #d4d4d4;
                        border: none;
                    }}
                    QTreeView::item:selected {{
                        background-color: rgba(60, 60, 60, {self._bg_opacity});
                    }}
                    QWidget {{
                        background-color: rgba({bg_color}, {self._bg_opacity});
                    }}
                """
                )
        else:
            if is_editor:
                widget.setStyleSheet(
                    f"""
                    QPlainTextEdit {{
                        background-color: rgb({bg_color});
                        border: none;
                    }}
                """
                )
            else:
                widget.setStyleSheet(
                    f"""
                    QTreeView {{
                        background-color: rgb({bg_color});
                        color: #d4d4d4;
                        border: none;
                    }}
                    QTreeView::item:selected {{
                        background-color: rgb(60, 60, 60);
                    }}
                    QWidget {{
                        background-color: rgb({bg_color});
                    }}
                """
                )

    def _setup_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        open_project_action = QAction("Open Project", self)
        open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_project_action.triggered.connect(self._open_project)
        file_menu.addAction(open_project_action)

        open_action = QAction("Open File", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._save_file)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menubar.addMenu("Edit")

        format_action = QAction("Format Document", self)
        format_action.setShortcut(QKeySequence("Ctrl+Alt+F"))
        format_action.triggered.connect(self._format_document)
        edit_menu.addAction(format_action)

        view_menu = menubar.addMenu("View")

        toggle_diag_action = QAction("Toggle Diagnostics Panel", self)
        toggle_diag_action.setShortcut(QKeySequence("Ctrl+D"))
        toggle_diag_action.triggered.connect(self._toggle_diagnostics_panel)
        view_menu.addAction(toggle_diag_action)

        toggle_terminal_action = QAction("Toggle Terminal", self)
        toggle_terminal_action.setShortcut(QKeySequence("Ctrl+`"))
        toggle_terminal_action.triggered.connect(self._toggle_terminal)
        view_menu.addAction(toggle_terminal_action)

        theme_action = QAction("Syntax Highlighting Colors", self)
        theme_action.triggered.connect(self._open_theme_picker)
        view_menu.addAction(theme_action)

        view_menu.addSeparator()

        bg_settings_action = QAction("Background Settings", self)
        bg_settings_action.triggered.connect(self._open_bg_settings)
        view_menu.addAction(bg_settings_action)

        build_menu = menubar.addMenu("Build")

        build_settings_action = QAction("Build Settings", self)
        build_settings_action.triggered.connect(self._open_build_settings)
        build_menu.addAction(build_settings_action)

        build_action = QAction("Build", self)
        build_action.setShortcut(QKeySequence("Ctrl+B"))
        build_action.triggered.connect(self._build_project)
        build_menu.addAction(build_action)

        run_action = QAction("Run", self)
        run_action.setShortcut(QKeySequence("Ctrl+R"))
        run_action.triggered.connect(self._run_project)
        build_menu.addAction(run_action)

        git_menu = menubar.addMenu("Git")

        lazygit_action = QAction("Open Lazygit", self)
        lazygit_action.setShortcut(QKeySequence("Ctrl+K"))
        lazygit_action.triggered.connect(self._open_git)
        git_menu.addAction(lazygit_action)

    def _setup_editor(self):
        self._editor.text_changed.connect(self._on_text_changed)
        self._editor.cursor_position_changed.connect(self._on_cursor_changed)
        self._editor.completion_requested.connect(self._on_completion_requested)

        self._editor.quick_fix_requested.connect(self._on_quick_fix_requested)
        self._editor.format_requested.connect(self._format_document)

        self._lsp_integration.completion_ready.connect(self._on_completion_ready)
        self._lsp_integration.hover_ready.connect(self._on_hover_ready)
        self._lsp_integration.diagnostics_updated.connect(self._on_diagnostics_updated)

        self._completer = None

    def _setup_statusbar(self):
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._statusbar.showMessage("Ready")

    def _setup_timers(self):
        self._lsp_timer = QTimer()
        self._lsp_timer.timeout.connect(self._process_lsp_events)
        self._lsp_timer.start(1000)

    @pyqtSlot(Path)
    def _on_file_selected(self, path: Path):
        try:
            if self._current_file:
                supported_extensions = {
                    ".cpp",
                    ".h",
                    ".hpp",
                    ".c",
                    ".cc",
                    ".cxx",
                    ".hxx",
                }
                if self._current_file.suffix.lower() in supported_extensions:
                    self._lsp_integration.close_file(self._current_file)

            if self._editor.load_file(path):
                self._current_file = path

                supported_extensions = {
                    ".cpp",
                    ".h",
                    ".hpp",
                    ".c",
                    ".cc",
                    ".cxx",
                    ".hxx",
                }

                if path.suffix.lower() in supported_extensions:
                    content = self._editor.toPlainText()
                    self._lsp_integration.open_file(path, content)
                    self._statusbar.showMessage(f"Opened: {path.name} (with LSP)")
                else:
                    self._statusbar.showMessage(f"Opened: {path.name} (no LSP)")

        except Exception as e:
            log(f"failed to open file {path}: {e}")

    @pyqtSlot(str)
    def _on_text_changed(self, text: str):
        if self._current_file:
            supported_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if self._current_file.suffix.lower() in supported_extensions:
                self._lsp_integration.change_file(self._current_file, text)

    @pyqtSlot(int, int)
    def _on_cursor_changed(self, line: int, column: int):
        self._statusbar.showMessage(f"Line: {line}, Column: {column}")

    @pyqtSlot(int, int)
    def _on_completion_requested(self, line: int, character: int):
        if self._current_file:
            supported_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if self._current_file.suffix.lower() in supported_extensions:
                self._lsp_integration.request_completion(
                    self._current_file, line, character
                )

    @pyqtSlot(int, int)
    def _on_quick_fix_requested(self, line: int, character: int):
        pass

    @pyqtSlot(list)
    def _on_completion_ready(self, completions: list):
        if self._completer:
            self._completer.update_completions(completions)

    @pyqtSlot(str)
    def _on_hover_ready(self, content: str):
        self._statusbar.showMessage(f"Hover: {content[:50]}...")

    @pyqtSlot(list)
    def _on_diagnostics_updated(self, diagnostics: list):
        if self._current_file:
            self._editor.update_diagnostics(diagnostics)
            self._diagnostics_panel.update_diagnostics(diagnostics)
        else:
            self._diagnostics_panel.update_diagnostics([])

    @pyqtSlot(int, int)
    def _on_diagnostic_clicked(self, line: int, character: int):
        self._editor.goto_position(line, character)

    def _toggle_diagnostics_panel(self):
        if self._diagnostics_panel.isVisible():
            self._diagnostics_panel.hide()
        else:
            self._diagnostics_panel.show()

    def _toggle_terminal(self):
        if self._terminal.isVisible():
            self._terminal.hide()
        else:
            self._terminal.show()

    def _process_lsp_events(self):
        try:
            self._lsp_integration.process_events()
        except Exception:
            pass

    def _open_project(self):
        try:
            directory = QFileDialog.getExistingDirectory(
                self, "Select Project Directory", str(self._project_path)
            )

            if directory:
                self._project_path = Path(directory)
                self._file_tree.set_root_path(self._project_path)
                self._editor.set_project_path(self._project_path)
                self._build_helper = BuildHelper(self._project_path)
                self.setWindowTitle(f"C++ Editor - {self._project_path.name}")
                self._statusbar.showMessage(
                    f"Project changed to: {self._project_path.name}"
                )

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
            self._on_file_selected(Path(file_path))

    def _save_file(self):
        if self._current_file and self._editor.save_file():
            supported_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if self._current_file.suffix.lower() in supported_extensions:
                self._lsp_integration.save_file(self._current_file)
            self._statusbar.showMessage(f"Saved: {self._current_file.name}")

    def _format_document(self):
        if not self._current_file:
            return

        supported_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
        if self._current_file.suffix.lower() not in supported_extensions:
            return

        edits = self._lsp_integration.format_document_in_memory(self._current_file)

        if edits:
            self._editor.apply_text_edits(edits)
            self._statusbar.showMessage("Formatted")

    def _open_theme_picker(self):
        from src.ui.theme_picker import ThemePicker

        if not self._theme_picker:
            self._theme_picker = ThemePicker(self._editor_config.colors, self)
            self._theme_picker.colors_changed.connect(self._on_colors_changed)
        self._theme_picker._theme_combo.setCurrentText(
            self._editor_config.colors.to_dict().get("name", "")
        )
        self._theme_picker.show()

    def _on_colors_changed(self, colors):
        self._editor_config.colors = colors
        self._editor_config.save()
        self._editor.set_colors(colors)

    def _open_bg_settings(self):
        from src.ui.bg_settings import BackgroundSettings

        if not self._bg_settings:
            self._bg_settings = BackgroundSettings(
                self._bg_enabled, self._bg_opacity, self._bg_brightness, self
            )
            self._bg_settings.settings_changed.connect(self._on_bg_settings_changed)
        self._bg_settings.show()

    def _on_bg_settings_changed(self, enabled: bool, opacity: int, brightness: float):
        self._bg_enabled = enabled
        self._bg_opacity = opacity
        self._bg_brightness = brightness

        if enabled:
            self._bg.show()
            self._bg.set_brightness(brightness)
        else:
            self._bg.hide()

        self._update_widget_style(self._file_tree)
        self._update_widget_style(self._editor, is_editor=True)
        self._update_widget_style(self._diagnostics_panel, bg_color="40, 40, 40")
        self._update_widget_style(self._terminal)

    def _open_build_settings(self):
        try:
            settings_dialog = BuildConfig(self._build_helper, self)
            if settings_dialog.exec():
                self._statusbar.showMessage("Build settings saved")

        except Exception as e:
            log(f"failed to open build settings: {e}")

    def _build_project(self):
        self._terminal.show()
        build_cmd = self._build_helper.get_build_command()
        self._terminal.execute_command(build_cmd)
        self._statusbar.showMessage("Building...")

    def _run_project(self):
        self._terminal.show()
        build_cmd = self._build_helper.get_build_command()
        run_cmd = self._build_helper.get_run_command()
        combined_cmd = f"{build_cmd} && {run_cmd}"
        self._terminal.execute_command(combined_cmd)
        self._statusbar.showMessage("Running...")

    def _open_git(self):
        try:
            GitHelper.open_lazygit(self._project_path)
        except Exception as e:
            log(f"failed to open git: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_bg"):
            self._bg.setGeometry(0, 0, self.width(), self.height())
        if hasattr(self, "_overlay"):
            self._overlay.setGeometry(0, 0, self.width(), self.height())

    def closeEvent(self, event):
        try:
            if self._current_file:
                supported_extensions = {
                    ".cpp",
                    ".h",
                    ".hpp",
                    ".c",
                    ".cc",
                    ".cxx",
                    ".hxx",
                }
                if self._current_file.suffix.lower() in supported_extensions:
                    self._lsp_integration.close_file(self._current_file)

            self._lsp_session.__exit__(None, None, None)

        except Exception as e:
            log(f"error during cleanup: {e}")

        event.accept()
