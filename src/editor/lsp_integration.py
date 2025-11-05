from pathlib import Path
from typing import Dict
import hashlib
from PyQt6.QtCore import QObject, pyqtSignal

from src.common.vars import log
from src.lsp_server.session import LspSession


class LspIntegration(QObject):
    diagnostics_updated = pyqtSignal(list)
    completion_ready = pyqtSignal(list)
    hover_ready = pyqtSignal(str)

    def __init__(self, session: LspSession):
        super().__init__()

        self._session = session
        self._opened_files: Dict[str, Path] = {}
        self._last_file_uri: str = None
        self._diagnostics_cache: Dict[str, str] = {}
        self._processing = False

    def open_file(self, path: Path, content: str = None):
        try:
            uri = path.as_uri()
            self._opened_files[uri] = path
            self._last_file_uri = uri

            self._session.open_file(str(path))

            self._diagnostics_cache[uri] = None

            log(f"lsp: opened file {path}")

        except Exception as e:
            log(f"lsp: failed to open file {path}: {e}")

    def close_file(self, path: Path):
        try:
            uri = path.as_uri()
            if uri in self._opened_files:
                self._session.close_file(str(path))
                del self._opened_files[uri]

                if self._last_file_uri == uri:
                    self._last_file_uri = None

                self._diagnostics_cache.pop(uri, None)

                log(f"lsp: closed file {path}")

        except Exception as e:
            log(f"lsp: failed to close file {path}: {e}")

    def save_file(self, path: Path):
        try:
            self._session.save_file(str(path))
            log(f"lsp: saved file {path}")

        except Exception as e:
            log(f"lsp: failed to save file {path}: {e}")

    def change_file(self, path: Path, content: str):
        try:
            uri = path.as_uri()

            if self._last_file_uri != uri:
                self._last_file_uri = uri

            self._session.on_text_change(str(path), content)

        except Exception as e:
            log(f"lsp: failed to change file {path}: {e}")

    def request_completion(self, path: Path, line: int, character: int):
        try:
            completion_list = self._session.get_completion(str(path), line, character)

            items = []
            if (
                completion_list
                and hasattr(completion_list, "items")
                and completion_list.items
            ):
                for item in completion_list.items:
                    items.append(
                        {
                            "label": item.label,
                            "kind": item.kind if item.kind else 0,
                            "detail": item.detail or "",
                            "documentation": (
                                str(item.documentation) if item.documentation else ""
                            ),
                            "sort_text": getattr(item, "sort_text", item.label),
                            "filter_text": getattr(item, "filter_text", item.label),
                        }
                    )

            self.completion_ready.emit(items)

        except Exception as e:
            log(f"lsp: failed to request completion: {e}")
            self.completion_ready.emit([])

    def request_hover(self, path: Path, line: int, character: int):
        try:
            hover = self._session.get_hover(str(path), line, character)

            content = ""
            if hover:
                if isinstance(hover, str):
                    content = hover
                elif hasattr(hover, "value"):
                    content = hover.value
                else:
                    content = str(hover)

            self.hover_ready.emit(content)

        except Exception as e:
            log(f"lsp: failed to request hover: {e}")
            self.hover_ready.emit("")

    def format_document(self, path: Path):
        try:
            result = self._session.format_document(str(path))
            if result:
                log(f"lsp: formatted {path}")
                return True

        except Exception as e:
            log(f"lsp: failed to request formatting: {e}")

        return False

    def process_events(self):
        if self._processing:
            return

        self._processing = True
        try:
            if not self._last_file_uri:
                return

            try:
                diagnostics_dict = self._session.get_diagnostics()
            except Exception as e:
                log(f"lsp: error getting diagnostics: {e}")
                return

            if not isinstance(diagnostics_dict, dict):
                return

            if self._last_file_uri not in diagnostics_dict:
                self.diagnostics_updated.emit([])
                self._diagnostics_cache[self._last_file_uri] = "EMPTY"
                return

            diags = diagnostics_dict[self._last_file_uri]

            if diags:
                diag_parts = []
                for d in sorted(
                    diags,
                    key=lambda x: (
                        x.range.start.line,
                        x.range.start.character,
                        x.message,
                    ),
                ):
                    key = (
                        d.range.start.line,
                        d.range.start.character,
                        d.range.end.line,
                        d.range.end.character,
                        d.message,
                        getattr(d, "severity", 1),
                    )
                    diag_parts.append(str(key))

                diag_hash = hashlib.md5(";".join(diag_parts).encode()).hexdigest()
            else:
                diag_hash = "EMPTY"

            cached_hash = self._diagnostics_cache.get(self._last_file_uri)

            if cached_hash == diag_hash:
                return

            self._diagnostics_cache[self._last_file_uri] = diag_hash

            diagnostic_list = []
            for diagnostic in diags:
                try:
                    diagnostic_list.append(
                        {
                            "line": diagnostic.range.start.line,
                            "character": diagnostic.range.start.character,
                            "end_line": diagnostic.range.end.line,
                            "end_character": diagnostic.range.end.character,
                            "severity": getattr(diagnostic, "severity", 1),
                            "message": diagnostic.message,
                            "code": getattr(diagnostic, "code", None),
                            "source": getattr(diagnostic, "source", None),
                        }
                    )
                except Exception as e:
                    log(f"lsp: error processing diagnostic: {e}")

            self.diagnostics_updated.emit(diagnostic_list)

        except Exception as e:
            log(f"lsp: error in process_events: {e}")

        finally:
            self._processing = False
