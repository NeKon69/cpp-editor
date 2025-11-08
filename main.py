import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
import qdarkstyle

from src.ui.main_window import MainWindow
from src.common.vars import log


def main():
    project_path = Path.cwd() / "lsp_test_project"

    if not project_path.exists():
        log(f"project path does not exist: {project_path}")
        return

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt5"))

    window = MainWindow(project_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
