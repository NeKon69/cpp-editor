import platform
from PyQt6.QtCore import Qt, pyqtSlot, QProcess, QProcessEnvironment, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor, QKeyEvent
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QLabel,
    QHBoxLayout,
    QPushButton,
)

MAX_BUFFER_SIZE = 5000


class TerminalWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._process = None
        self._working_dir = None
        self._command_start_pos = 0

        self._shell = (
            ("cmd.exe", ["/C"])
            if platform.system().lower() == "windows"
            else ("/bin/bash", ["-c"])
        )

        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumSize(100, 100)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)

        self._title_label = QLabel("Terminal", self)
        self._title_label.setStyleSheet(
            "background-color: #2d2d2d; color: white; padding: 4px;"
        )
        title_layout.addWidget(self._title_label)

        self._stop_btn = QPushButton("Stop (Ctrl+C)", self)
        self._stop_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; padding: 4px; border: none;"
        )
        self._stop_btn.clicked.connect(self._stop_process)
        self._stop_btn.setEnabled(False)
        title_layout.addWidget(self._stop_btn)

        layout.addLayout(title_layout)

        self._text_edit = QTextEdit(self)
        self._text_edit.setFont(QFont("JetBrainsMono Nerd Font", 10))
        self._text_edit.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: none;"
        )
        self._text_edit.installEventFilter(self)
        self._text_edit.setUndoRedoEnabled(False)
        self._text_edit.setAcceptRichText(False)
        layout.addWidget(self._text_edit, 1)

        self._append_prompt()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._text_edit.resize(self.width(), self.height() - self._title_label.height())

    def _append_prompt(self):
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self._text_edit.insertPlainText("\n$ ")
        self._command_start_pos = self._text_edit.textCursor().position()
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        QTimer.singleShot(50, self._text_edit.ensureCursorVisible)

    def eventFilter(self, obj, event):
        if obj == self._text_edit and event.type() == event.KeyPress:
            return self._handle_key_press(event)
        return super().eventFilter(obj, event)

    def _handle_key_press(self, event: QKeyEvent):
        cursor = self._text_edit.textCursor()
        pos = cursor.position()
        key = event.key()

        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            if pos <= self._command_start_pos:
                return True

        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            cmd = self._text_edit.toPlainText()[self._command_start_pos :]
            cmd = cmd.strip()
            self._text_edit.insertPlainText("\n")
            if cmd:
                self.execute_command(cmd)
            else:
                self._append_prompt()
            return True

        if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_Home):
            if pos <= self._command_start_pos:
                return True

        if pos < self._command_start_pos:
            cursor.setPosition(len(self._text_edit.toPlainText()))
            self._text_edit.setTextCursor(cursor)

        return False

    def set_working_dir(self, path):
        self._working_dir = str(path)

    def append_text(self, text: str, error: bool = False):
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self._text_edit.setTextColor(QColor("#ff5555") if error else QColor("#d4d4d4"))
        self._text_edit.insertPlainText(text + "\n")
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
        self._text_edit.ensureCursorVisible()
        QTimer.singleShot(50, self._text_edit.ensureCursorVisible)

        buf = self._text_edit.toPlainText()
        if len(buf) > MAX_BUFFER_SIZE:
            self._text_edit.setPlainText(buf[-MAX_BUFFER_SIZE:])
            self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
            self._text_edit.ensureCursorVisible()
            QTimer.singleShot(50, self._text_edit.ensureCursorVisible)

    def execute_command(self, command: str):
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self.append_text("[Process already running]", True)
            self._append_prompt()
            return

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

        shell_cmd, shell_args = self._shell
        self._process.start(shell_cmd, shell_args + [command])

    @pyqtSlot()
    def _handle_stdout(self):
        data = self._process.readAllStandardOutput().data().decode(errors="ignore")
        if data:
            self.append_text(data.rstrip())

    @pyqtSlot()
    def _handle_stderr(self):
        data = self._process.readAllStandardError().data().decode(errors="ignore")
        if data:
            self.append_text(data.rstrip(), True)

    @pyqtSlot(int, QProcess.ExitStatus)
    def _handle_finished(self, exit_code, exit_status):
        self._stop_btn.setEnabled(False)
        self.append_text(f"[Exit code: {exit_code}]", True)
        self._process = None
        self._append_prompt()

    def _stop_process(self):
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self.append_text("^C")
            self._process.kill()

    def set_title(self, title: str):
        self._title_label.setText(title)
