from pathlib import Path
from typing import Optional
import json
import sqlite3

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from src.common.vars import log
from src.common.global_settings_db import GlobalSettingsDB
from src.configs.editor_config import EditorConfig
from src.configs.build_config import BuildHelper
from src.editor.lsp_integration import LspIntegration
from src.editor.build_helper import BuildHelper
from src.lsp_server.session import LspSession


class MainBack(QObject):

    completion_ready = pyqtSignal(list)
    hover_ready = pyqtSignal(str)
    diagnostics_updated = pyqtSignal(list)
    file_opened = pyqtSignal(Path)
    file_saved = pyqtSignal(str)
    status_message = pyqtSignal(str)
    project_changed = pyqtSignal(Path)

    def __init__(self, project_path: Path, parent=None):
        super().__init__(parent)

        self._project_path = project_path
        self._current_file: Optional[Path] = None

        self._global_db = GlobalSettingsDB()
        self._migrate_global_settings()

        self._editor_config = EditorConfig.load(self._global_db)

        self._migrate_project_settings(project_path)
        self._build_helper = BuildHelper(project_path)

        self._completer = None

        self._setup_lsp()
        self._setup_timers()

    def _migrate_global_settings(self):
        old_config_path = Path.home() / ".cpp_editor_config.json"
        if not old_config_path.exists():
            return

        try:
            with open(old_config_path, "r") as f:
                data = json.load(f)

            self._global_db.set_setting(
                "font_family", data.get("font_family", "Fira Code")
            )
            self._global_db.set_setting("font_size", str(data.get("font_size", 11)))
            self._global_db.set_setting("tab_width", str(data.get("tab_width", 4)))

            colors_data = data.get("colors", {})
            if colors_data:
                theme_name = "Migrated Theme"
                self._global_db.save_theme(theme_name, colors_data)
                self._global_db.set_setting("active_theme", theme_name)

            old_config_path.rename(Path.home() / ".cpp_editor_config.json.migrated")
            log("global settings migrated successfully")

        except Exception as e:
            log(f"failed to migrate global settings: {e}")

    def _migrate_project_settings(self, project_path: Path):
        old_db_path = project_path / ".build_settings.sqlite"
        if not old_db_path.exists():
            return

        try:
            conn = sqlite3.connect(old_db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT build_command, run_command FROM build_settings WHERE id = 1"
            )
            result = cursor.fetchone()
            conn.close()

            if result:
                build_cmd, run_cmd = result
                helper = BuildHelper(project_path)
                helper.set_build_command(build_cmd)
                helper.set_run_command(run_cmd)

            old_db_path.rename(project_path / ".build_settings.sqlite.migrated")
            log("project settings migrated successfully")

        except Exception as e:
            log(f"failed to migrate project settings: {e}")

    def _setup_lsp(self):
        try:
            self._lsp_session = LspSession(str(self._project_path))
            self._lsp_session.__enter__()

            self._lsp_integration = LspIntegration(self._lsp_session)

            self._lsp_integration.completion_ready.connect(self.completion_ready.emit)
            self._lsp_integration.hover_ready.connect(self.hover_ready.emit)
            self._lsp_integration.diagnostics_updated.connect(
                self._on_diagnostics_updated
            )

            log("lsp session initialized")

        except Exception as e:
            log(f"failed to initialize lsp: {e}")

    def _setup_timers(self):
        self._lsp_timer = QTimer()
        self._lsp_timer.timeout.connect(self._process_lsp_events)
        self._lsp_timer.start(1000)

    def init_completer(self, editor):
        from src.editor.completer import LspCompleter

        self._completer = LspCompleter(editor)
        self.completion_ready.connect(self._completer.update_completions)

    @pyqtSlot(Path)
    def on_file_selected(self, path: Path):
        try:
            if self._current_file:
                if self._is_supported_file(self._current_file):
                    self._lsp_integration.close_file(self._current_file)

            self._current_file = path
            self.file_opened.emit(path)

            if self._is_supported_file(path):
                self.status_message.emit(f"Opened: {path.name} (with LSP)")
            else:
                self.status_message.emit(f"Opened: {path.name} (no LSP)")

        except Exception as e:
            log(f"failed to open file {path}: {e}")

    def on_file_loaded(self, path: Path, content: str):
        if self._is_supported_file(path):
            self._lsp_integration.open_file(path, content)

    @pyqtSlot(str)
    def on_text_changed(self, text: str):
        if self._current_file and self._is_supported_file(self._current_file):
            self._lsp_integration.change_file(self._current_file, text)

    @pyqtSlot(int, int)
    def on_completion_requested(self, line: int, character: int):
        if self._current_file and self._is_supported_file(self._current_file):
            self._lsp_integration.request_completion(
                self._current_file, line, character
            )

    @pyqtSlot(list)
    def _on_diagnostics_updated(self, diagnostics: list):
        self.diagnostics_updated.emit(diagnostics)

    def _process_lsp_events(self):
        try:
            self._lsp_integration.process_events()
        except Exception:
            pass

    def _is_supported_file(self, path: Path) -> bool:
        supported_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
        return path.suffix.lower() in supported_extensions

    def save_file(self):
        if self._current_file:
            if self._is_supported_file(self._current_file):
                self._lsp_integration.save_file(self._current_file)
            self.file_saved.emit(self._current_file.name)

    def format_document(self):
        if not self._current_file:
            return None

        if not self._is_supported_file(self._current_file):
            return None

        edits = self._lsp_integration.format_document_in_memory(self._current_file)

        if edits:
            self.status_message.emit("Formatted")

        return edits

    def change_project(self, path: Path):
        self._project_path = path
        self._migrate_project_settings(path)
        self._build_helper = BuildHelper(path)
        self.project_changed.emit(path)

    def build_project(self):
        build_cmd = self._build_helper.get_build_command()
        self.status_message.emit("Building...")
        return build_cmd

    def run_project(self):
        build_cmd = self._build_helper.get_build_command()
        run_cmd = self._build_helper.get_run_command()
        combined_cmd = f"{build_cmd} && {run_cmd}"
        self.status_message.emit("Running...")
        return combined_cmd

    def cleanup(self):
        try:
            if self._current_file:
                if self._is_supported_file(self._current_file):
                    self._lsp_integration.close_file(self._current_file)

            self._lsp_session.__exit__(None, None, None)

        except Exception as e:
            log(f"error during cleanup: {e}")

    def get_editor_config(self):
        return self._editor_config

    def get_build_helper(self):
        return self._build_helper

    def get_project_path(self):
        return self._project_path

    def get_global_db(self):
        return self._global_db
