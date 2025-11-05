from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QDir, pyqtSignal
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtGui import QFileSystemModel

from src.common.vars import log


class FileTree(QTreeView):
    file_selected = pyqtSignal(Path)

    def __init__(self, root_path: Optional[Path] = None):
        super().__init__()

        self._model = QFileSystemModel()
        self._root_path = root_path

        self._setup_model()
        self._setup_view()

    def _setup_model(self):
        self._model.setRootPath(QDir.rootPath())
        self._model.setFilter(
            QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot
        )

        self.setModel(self._model)

    def _setup_view(self):
        self.setAnimated(True)
        self.setIndentation(20)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        for i in range(1, 4):
            self.hideColumn(i)

        self.clicked.connect(self._on_file_clicked)

        if self._root_path:
            self.set_root_path(self._root_path)

    def set_root_path(self, path: Path):
        try:
            self._root_path = path
            index = self._model.index(str(path))
            self.setRootIndex(index)

            log(f"file tree root set to: {path}")

        except Exception as e:
            log(f"failed to set root path {path}: {e}")

    def _on_file_clicked(self, index):
        try:
            file_path = Path(self._model.filePath(index))

            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in [".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"]:
                    self.file_selected.emit(file_path)
                    log(f"file selected: {file_path}")

        except Exception as e:
            log(f"failed to handle file click: {e}")
