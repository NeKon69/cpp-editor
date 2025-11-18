import sys, os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
import qdarkstyle

from src.ui.main_window import MainWindow
from src.common.vars import log


def main():
    if len(sys.argv) > 1:
        project_path = Path(sys.argv[1])
    else:
        project_path = Path.cwd()

    if not os.path.isdir(project_path):
        log(f"project path does not exist: {project_path}")
        project_path = Path.cwd()

    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api="pyqt6"))

    window = MainWindow(project_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
