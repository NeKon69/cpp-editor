from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSplitter,
)

from src.configs.editor_config import EditorConfig
from src.editor.editor_widget import CodeEditor
from src.ui.file_tree import FileTree
from src.ui.diagnostics_panel import DiagnosticsPanel
from src.ui.terminal_widget import TerminalWidget


class MainFront(QWidget):

    file_selected = pyqtSignal(Path)
    diagnostic_clicked = pyqtSignal(int, int)

    open_project_requested = pyqtSignal()
    save_requested = pyqtSignal()
    format_requested = pyqtSignal()
    build_requested = pyqtSignal()
    run_requested = pyqtSignal()

    theme_picker_requested = pyqtSignal()
    bg_settings_requested = pyqtSignal()
    build_settings_requested = pyqtSignal()

    def __init__(self, project_path: Path, editor_config: EditorConfig, parent=None):
        super().__init__(parent)

        self._project_path = project_path
        self._editor_config = editor_config

        self._bg_enabled = False
        self._bg_opacity = 200
        self._bg_brightness = 0.6

        self._setup_ui()

    def _setup_ui(self):
        from src.ui.shader_bg import OpenGLBackground

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        self._bg = OpenGLBackground(container)
        self._bg.set_brightness(self._bg_brightness)
        self._bg.lower()
        self._bg.hide()

        self._setup_widgets()

        overlay_widget = QWidget(container)
        overlay_widget.setLayout(self._create_main_layout())
        overlay_widget.setStyleSheet("background: transparent;")
        overlay_widget.raise_()

        self._overlay = overlay_widget

        main_layout.addWidget(container)

    def _setup_widgets(self):
        self._file_tree = FileTree(self._project_path)
        self._file_tree.file_selected.connect(self.file_selected.emit)
        self._file_tree.setMinimumWidth(200)
        self._file_tree.setMaximumWidth(400)
        self._update_widget_style(self._file_tree)

        self._editor = CodeEditor(self._editor_config)
        self._editor.set_project_path(self._project_path)
        self._editor.set_colors(self._editor_config.colors)
        self._update_widget_style(self._editor, is_editor=True)

        self._diagnostics_panel = DiagnosticsPanel()
        self._diagnostics_panel.diagnostic_clicked.connect(self.diagnostic_clicked.emit)
        self._diagnostics_panel.hide()
        self._update_widget_style(self._diagnostics_panel, bg_color="40, 40, 40")

        self._terminal = TerminalWidget()
        self._terminal.set_working_dir(self._project_path)
        self._terminal.setMaximumHeight(1000)
        self._terminal.hide()
        self._update_widget_style(self._terminal)

    def _create_main_layout(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.setHandleWidth(1)
        main_splitter.setStyleSheet("QSplitter { background: transparent; }")

        h_splitter = self._create_horizontal_splitter()

        main_splitter.addWidget(h_splitter)
        main_splitter.addWidget(self._terminal)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 0)

        layout.addWidget(main_splitter)

        return layout

    def _create_horizontal_splitter(self):
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(1)
        h_splitter.setStyleSheet("QSplitter { background: transparent; }")

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(1)
        v_splitter.setStyleSheet("QSplitter { background: transparent; }")

        v_splitter.addWidget(self._editor)
        v_splitter.addWidget(self._diagnostics_panel)
        v_splitter.setStretchFactor(0, 1)
        v_splitter.setStretchFactor(1, 0)

        h_splitter.addWidget(self._file_tree)
        h_splitter.addWidget(v_splitter)
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)

        return h_splitter

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

    def setup_menubar(self, menubar):
        file_menu = menubar.addMenu("File")

        open_project_action = QAction("Open Project", self)
        open_project_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        open_project_action.triggered.connect(self.open_project_requested.emit)
        file_menu.addAction(open_project_action)

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_requested.emit)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.parent().close)
        file_menu.addAction(exit_action)

        self._setup_edit_menu(menubar)
        self._setup_view_menu(menubar)
        self._setup_build_menu(menubar)

    def _setup_edit_menu(self, menubar):
        edit_menu = menubar.addMenu("Edit")

        format_action = QAction("Format Document", self)
        format_action.setShortcut(QKeySequence("Ctrl+Alt+F"))
        format_action.triggered.connect(self.format_requested.emit)
        edit_menu.addAction(format_action)

    def _setup_view_menu(self, menubar):
        view_menu = menubar.addMenu("View")

        toggle_diag_action = QAction("Toggle Diagnostics Panel", self)
        toggle_diag_action.setShortcut(QKeySequence("Ctrl+D"))
        toggle_diag_action.triggered.connect(self.toggle_diagnostics_panel)
        view_menu.addAction(toggle_diag_action)

        toggle_terminal_action = QAction("Toggle Terminal", self)
        toggle_terminal_action.setShortcut(QKeySequence("Ctrl+`"))
        toggle_terminal_action.triggered.connect(self.toggle_terminal)
        view_menu.addAction(toggle_terminal_action)

        theme_action = QAction("Syntax Highlighting Colors", self)
        theme_action.triggered.connect(self.theme_picker_requested.emit)
        view_menu.addAction(theme_action)

        view_menu.addSeparator()

        bg_settings_action = QAction("Background Settings", self)
        bg_settings_action.triggered.connect(self.bg_settings_requested.emit)
        view_menu.addAction(bg_settings_action)

    def _setup_build_menu(self, menubar):
        build_menu = menubar.addMenu("Build")

        build_settings_action = QAction("Build Settings", self)
        build_settings_action.triggered.connect(self.build_settings_requested.emit)
        build_menu.addAction(build_settings_action)

        build_action = QAction("Build", self)
        build_action.setShortcut(QKeySequence("Ctrl+B"))
        build_action.triggered.connect(self.build_requested.emit)
        build_menu.addAction(build_action)

        run_action = QAction("Run", self)
        run_action.setShortcut(QKeySequence("Ctrl+R"))
        run_action.triggered.connect(self.run_requested.emit)
        build_menu.addAction(run_action)

    def toggle_diagnostics_panel(self):
        if self._diagnostics_panel.isVisible():
            self._diagnostics_panel.hide()
        else:
            self._diagnostics_panel.show()

    def toggle_terminal(self):
        if self._terminal.isVisible():
            self._terminal.hide()
        else:
            self._terminal.show()

    def update_bg_settings(self, enabled: bool, opacity: int, brightness: float):
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

    def update_colors(self, colors):
        self._editor_config.colors = colors
        self._editor.set_colors(colors)

    def set_root_path(self, path: Path):
        self._project_path = path
        self._file_tree.set_root_path(path)
        self._editor.set_project_path(path)
        self._terminal.set_working_dir(path)

    def resize_background(self, width: int, height: int):
        self._bg.setGeometry(0, 0, width, height)
        self._overlay.setGeometry(0, 0, width, height)

    def get_editor(self):
        return self._editor

    def get_diagnostics_panel(self):
        return self._diagnostics_panel

    def get_terminal(self):
        return self._terminal

    def show_terminal(self):
        self._terminal.show()

    def get_bg_settings(self):
        return self._bg_enabled, self._bg_opacity, self._bg_brightness
