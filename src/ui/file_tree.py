from pathlib import Path
from PyQt6.QtWidgets import (
    QTreeView,
    QMenu,
    QInputDialog,
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QHBoxLayout,
)
from PyQt6.QtCore import pyqtSignal, Qt, QModelIndex
from PyQt6.QtGui import QAction, QFileSystemModel


class NewFileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New C++ File")
        self.setModal(True)

        layout = QVBoxLayout()

        self._label = QLabel(
            "Enter filename with extension (.cpp, .h, .hpp, .c, .cc, .cxx, .hxx):"
        )
        layout.addWidget(self._label)

        self._input = QLineEdit()
        self._input.setPlaceholderText("example.cpp")
        layout.addWidget(self._input)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()
        layout.addWidget(self._error_label)

        btn_layout = QHBoxLayout()
        self._ok_btn = QPushButton("Create")
        self._ok_btn.clicked.connect(self._on_ok)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._ok_btn)
        btn_layout.addWidget(self._cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.filename = None

    def _on_ok(self):
        name = self._input.text().strip()
        if not name:
            self._error_label.setText("Filename cannot be empty")
            self._error_label.show()
            return

        allowed_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
        has_valid_ext = any(name.endswith(ext) for ext in allowed_extensions)

        if not has_valid_ext:
            self._error_label.setText("only the best language is allowed")
            self._error_label.show()
            return

        self.filename = name
        self.accept()


class FileTree(QTreeView):
    file_selected = pyqtSignal(Path)

    def __init__(self, root_path: Path, parent=None):
        super().__init__(parent)
        self._root_path = root_path
        self._model = QFileSystemModel()
        self._model.setRootPath(str(root_path))

        self.setModel(self._model)
        self.setRootIndex(self._model.index(str(root_path)))

        for i in range(1, 4):
            self.hideColumn(i)

        self.clicked.connect(self._on_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _on_clicked(self, index: QModelIndex):
        path = Path(self._model.filePath(index))
        if path.is_file():
            allowed_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if path.suffix.lower() in allowed_extensions:
                self.file_selected.emit(path)

    def set_root_path(self, path: Path):
        self._root_path = path
        self._model.setRootPath(str(path))
        self.setRootIndex(self._model.index(str(path)))

    def _show_context_menu(self, position):
        index = self.indexAt(position)
        menu = QMenu(self)

        if index.isValid():
            path = Path(self._model.filePath(index))

            allowed_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if path.suffix.lower() in allowed_extensions:
                rename_action = QAction("Rename", self)
                rename_action.triggered.connect(lambda: self._rename_item(path))
                menu.addAction(rename_action)

                delete_action = QAction("Delete", self)
                delete_action.triggered.connect(lambda: self._delete_item(path))
                menu.addAction(delete_action)

                menu.addSeparator()

        new_file_action = QAction("New C++ File", self)
        new_file_action.triggered.connect(lambda: self._create_file(index))
        menu.addAction(new_file_action)

        menu.exec(self.viewport().mapToGlobal(position))

    def _create_file(self, index: QModelIndex):
        if index.isValid():
            parent_path = Path(self._model.filePath(index))
            if parent_path.is_file():
                parent_path = parent_path.parent
        else:
            parent_path = self._root_path

        dialog = NewFileDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.filename:
            new_file = parent_path / dialog.filename
            try:
                new_file.touch()
                self.file_selected.emit(new_file)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create file: {e}")

    def _rename_item(self, path: Path):
        old_name = path.name
        new_name, ok = QInputDialog.getText(
            self, "Rename", "Enter new name:", text=old_name
        )

        if ok and new_name and new_name != old_name:
            allowed_extensions = {".cpp", ".h", ".hpp", ".c", ".cc", ".cxx", ".hxx"}
            if not any(new_name.endswith(ext) for ext in allowed_extensions):
                QMessageBox.critical(self, "Error", "only the best language is allowed")
                return

            new_path = path.parent / new_name
            try:
                path.rename(new_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to rename: {e}")

    def _delete_item(self, path: Path):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete {path.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if path.is_dir():
                    import shutil

                    shutil.rmtree(path)
                else:
                    path.unlink()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete: {e}")
