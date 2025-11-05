from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QSize
from PyQt6.QtGui import QAction, QKeySequence, QColor
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QFileDialog,
    QStatusBar,
    QMenuBar,
    QColorDialog,
    QMessageBox,
)

from src.common.vars import log
from src.configs.editor_config import EditorConfig
from src.editor.editor_widget import CodeEditor
from src.editor.lsp_integration import LspIntegration
from src.editor.completer import LspCompleter
from src.lsp_server.session import LspSession
from src.ui.file_tree import FileTree
from src.ui.diagnostics_panel import DiagnosticsPanel
from src.utils.git_helper import GitHelper


class MainWindow(QMainWindow):
    def __init__(self, project_path: Path):
        super().__init__()

        self._project_path = project_path
        self._current_file: Optional[Path] = None
        self._editor_config = EditorConfig()

        self._setup_window()
        self._setup_lsp()
        self._setup_ui()
        self._setup_menubar()
        self._setup_editor()
        self._setup_statusbar()
        self._setup_timers()

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
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(1)

        self._file_tree = FileTree(self._project_path)
        self._file_tree.file_selected.connect(self._on_file_selected)
        self._file_tree.setMinimumWidth(200)
        self._file_tree.setMaximumWidth(400)

        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.setHandleWidth(1)

        self._editor = CodeEditor(self._editor_config)

        self._diagnostics_panel = DiagnosticsPanel()
        self._diagnostics_panel.diagnostic_clicked.connect(self._on_diagnostic_clicked)
        self._diagnostics_panel.hide()

        v_splitter.addWidget(self._editor)
        v_splitter.addWidget(self._diagnostics_panel)
        v_splitter.setStretchFactor(0, 1)
        v_splitter.setStretchFactor(1, 0)

        h_splitter.addWidget(self._file_tree)
        h_splitter.addWidget(v_splitter)
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)
        h_splitter.setSizes([250, 1350])

        main_layout.addWidget(h_splitter)

    def _setup_menubar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")

        open_action = QAction("Open", self)
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
        format_action.setShortcut(QKeySequence("Ctrl+Alt+L"))
        format_action.triggered.connect(self._format_document)
        edit_menu.addAction(format_action)

        view_menu = menubar.addMenu("View")

        toggle_diag_action = QAction("Toggle Diagnostics Panel", self)
        toggle_diag_action.setShortcut(QKeySequence("Ctrl+D"))
        toggle_diag_action.triggered.connect(self._toggle_diagnostics_panel)
        view_menu.addAction(toggle_diag_action)

        git_menu = menubar.addMenu("Git")

        lazygit_action = QAction("Open Lazygit", self)
        lazygit_action.setShortcut(QKeySequence("Ctrl+K"))
        lazygit_action.triggered.connect(self._open_git)
        git_menu.addAction(lazygit_action)

    def _setup_editor(self):
        self._completer = LspCompleter(self._editor)

        self._editor.text_changed.connect(self._on_text_changed)
        self._editor.cursor_position_changed.connect(self._on_cursor_changed)
        self._editor.completion_requested.connect(self._on_completion_requested)
        self._editor.quick_fix_requested.connect(self._on_quick_fix_requested)

        self._lsp_integration.completion_ready.connect(self._on_completion_ready)
        self._lsp_integration.hover_ready.connect(self._on_hover_ready)
        self._lsp_integration.diagnostics_updated.connect(self._on_diagnostics_updated)

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
        if self._current_file:
            supported_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if self._current_file.suffix.lower() in supported_extensions:
                QMessageBox.information(
                    self, "Quick Fix", "Code actions not yet fully supported"
                )

    @pyqtSlot(list)
    def _on_completion_ready(self, completions: list):
        self._completer.update_completions(completions)

    @pyqtSlot(str)
    def _on_hover_ready(self, content: str):
        self._statusbar.showMessage(f"Hover: {content[:50]}...")

    @pyqtSlot(list)
    def _on_diagnostics_updated(self, diagnostics: list):
        print(
            f"[MainWindow._on_diagnostics_updated] Received {len(diagnostics)} diagnostics"
        )

        for i, d in enumerate(diagnostics):
            print(f"  [{i}] L{d['line']+1}: {d['message']}")

        if self._current_file:
            print(
                f"[MainWindow._on_diagnostics_updated] Current file: {self._current_file}"
            )
            self._editor.update_diagnostics(diagnostics)
            self._diagnostics_panel.update_diagnostics(diagnostics)
        else:
            print(f"[MainWindow._on_diagnostics_updated] No current file!")
            self._diagnostics_panel.update_diagnostics([])

    @pyqtSlot(int, int)
    def _on_diagnostic_clicked(self, line: int, character: int):
        self._editor.goto_position(line, character)

    def _toggle_diagnostics_panel(self):
        if self._diagnostics_panel.isVisible():
            self._diagnostics_panel.hide()
        else:
            self._diagnostics_panel.show()

    def _process_lsp_events(self):
        try:
            self._lsp_integration.process_events()
        except Exception as e:
            pass

    def _open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File", str(self._project_path), "All Files (*)"
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
        if self._current_file:
            supported_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if self._current_file.suffix.lower() in supported_extensions:
                self._lsp_integration.format_document(self._current_file)
                self._statusbar.showMessage("Formatting...")
            else:
                self._statusbar.showMessage(
                    "Formatting not supported for this file type"
                )

    def _open_git(self):
        try:
            GitHelper.open_lazygit(self._project_path)
        except Exception as e:
            log(f"failed to open git: {e}")

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
