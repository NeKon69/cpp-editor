import platform
import os
import signal
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot, QProcess, QProcessEnvironment
from PyQt6.QtGui import QFont, QTextCursor, QKeyEvent, QColor
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QLabel,
    QLineEdit,
    QHBoxLayout,
    QPushButton,
)

from src.common.vars import log


class TerminalWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._process = None
        self._working_dir = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel("Terminal")
        self._title_label.setStyleSheet(
            "background-color: #2d2d2d; color: #ffffff; padding: 4px;"
        )
        title_layout.addWidget(self._title_label)

        self._stop_btn = QPushButton("Stop (Ctrl+C)")
        self._stop_btn.setStyleSheet(
            "background-color: #d32f2f; color: #ffffff; padding: 4px; border: none;"
        )
        self._stop_btn.clicked.connect(self._stop_process)
        self._stop_btn.setEnabled(False)
        title_layout.addWidget(self._stop_btn)

        title_widget = QWidget()
        title_widget.setLayout(title_layout)
        layout.addWidget(title_widget)

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)

        font = QFont("JetBrainsMono Nerd Font", 10)
        if not font.exactMatch():
            font = QFont("JetBrains Mono", 10)
        if not font.exactMatch():
            font = QFont("Consolas", 10)

        self._text_edit.setFont(font)
        self._text_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: none;"
        )
        layout.addWidget(self._text_edit)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(4, 4, 4, 4)

        self._prompt_label = QLabel("$")
        self._prompt_label.setStyleSheet("color: #00ff00;")
        input_layout.addWidget(self._prompt_label)

        self._input_line = QLineEdit()
        self._input_line.setFont(font)
        self._input_line.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #3e3e3e;"
        )
        self._input_line.returnPressed.connect(self._on_return_pressed)
        input_layout.addWidget(self._input_line)

        layout.addLayout(input_layout)

        self.setLayout(layout)

    def set_working_dir(self, path):
        self._working_dir = str(path)

    def _on_return_pressed(self):
        command = self._input_line.text().strip()
        if not command:
            return

        self._input_line.clear()
        self.execute_command(command)

    def _stop_process(self):
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self.append_text("^C", False)
            self._process.kill()

    def set_title(self, title: str):
        self._title_label.setText(title)

    def clear(self):
        self._text_edit.clear()

    def append_text(self, text: str, error: bool = False):
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        if error:
            self._text_edit.setTextColor(QColor("#ff5555"))
        else:
            self._text_edit.setTextColor(QColor("#d4d4d4"))
        self._text_edit.insertPlainText(text + "\n")
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)

    def execute_command(self, command: str):
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self.append_text("[Process already running]", True)
            return

        self.append_text(f"$ {command}", False)

        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._handle_stdout)
        self._process.readyReadStandardError.connect(self._handle_stderr)
        self._process.finished.connect(self._handle_finished)
        self._process.started.connect(lambda: self._stop_btn.setEnabled(True))

        if self._working_dir:
            self._process.setWorkingDirectory(self._working_dir)

        env = QProcessEnvironment.systemEnvironment()
        env.insert("TERM", "dumb")
        env.insert("NO_COLOR", "1")
        self._process.setProcessEnvironment(env)

        system = platform.system().lower()
        if system == "windows":
            self._process.start("powershell.exe", ["-Command", command])
        else:
            self._process.start("/bin/bash", ["-c", command])

    @pyqtSlot()
    def _handle_stdout(self):
        data = self._process.readAllStandardOutput().data().decode(errors="ignore")
        if data.strip():
            self.append_text(data.rstrip(), False)

    @pyqtSlot()
    def _handle_stderr(self):
        data = self._process.readAllStandardError().data().decode(errors="ignore")
        if data.strip():
            self.append_text(data.rstrip(), True)

    @pyqtSlot(int, QProcess.ExitStatus)
    def _handle_finished(self, exit_code, exit_status):
        self._stop_btn.setEnabled(False)
        if exit_code != 0:
            self.append_text(f"[Exit code: {exit_code}]", True)
        self._process = None

    def closeEvent(self, event):
        if self._process:
            self._process.kill()
            self._process.waitForFinished()
        event.accept()
