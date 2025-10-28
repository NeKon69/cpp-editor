from typing import List
import subprocess
import time
import os
import json
from pathlib import Path
import shutil
import sys
import sansio_lsp_client as lsp

# Later will be replaced with nvim client log
log = print


class ClangdNotFoundError(FileNotFoundError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class OpenedFile:
    def __init__(self, path: str):
        self.path: str = path
        self.contents: List[str] = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.contents = f.readlines()
        except FileNotFoundError:
            with open(path, "w", encoding="utf-8") as f:
                pass
            log(f"Created new file: {path}")
        except (IOError, PermissionError) as e:
            log(f"Error reading file {path}: {e}")
        except Exception as e:
            log(f"An unexpected error occurred while opening {path}: {e}")

    def __str__(self):
        return "".join(self.contents)

    def insert(self, position: lsp.Position, text: str):
        lines_to_insert = text.splitlines(True)

        if not lines_to_insert:
            return

        while position.line >= len(self.contents):
            self.contents.append("\n")

        if self.contents and not self.contents[-1].endswith("\n"):
            self.contents[-1] += "\n"

        original_line = self.contents[position.line]
        original_line_content = original_line.rstrip("\n")

        char_pos = min(position.character, len(original_line_content))

        before_text = original_line_content[:char_pos]
        after_text = original_line_content[char_pos:]

        lines_to_insert[0] = before_text + lines_to_insert[0]

        if not lines_to_insert[-1].endswith("\n"):
            lines_to_insert[-1] += after_text
        else:
            lines_to_insert.append(after_text + "\n")

        self.contents[position.line : position.line + 1] = lines_to_insert

    def apply_edit(self, edit: lsp.TextEdit):
        start = edit.range.start
        end = edit.range.end
        new_lines = edit.newText.splitlines(True)

        if not new_lines:
            new_lines = [""]

        line_before = self.contents[start.line][: start.character]
        line_after = self.contents[end.line][end.character :]

        new_lines[0] = line_before + new_lines[0]
        new_lines[-1] = new_lines[-1].rstrip("\r\n") + line_after

        self.contents[start.line : end.line + 1] = new_lines

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("".join(self.contents))
            log(f"File saved: {self.path}")
        except (IOError, PermissionError) as e:
            log(f"Error saving file {self.path}: {e}")


class ClangdProcess:
    def __init__(self, project_path: str, lsp_client=None):
        self.project_path = project_path
        self.process = None
        self.lsp_client = lsp_client

    def __enter__(self):
        try:
            self.process = subprocess.Popen(
                ["clangd", "-log=verbose", "--background-index"],
                cwd=self.project_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
            os.set_blocking(self.process.stdout.fileno(), False)
            os.set_blocking(self.process.stderr.fileno(), False)

        except FileNotFoundError as e:
            raise ClangdNotFoundError() from e
        except Exception as e:
            raise RuntimeError(f"Wasn't able to start clangd: {e}") from e

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not self.process or self.process.poll() is not None:
            return

        if self.lsp_client:
            try:
                self.lsp_client.shutdown()
                self.process.stdin.write(self.lsp_client.send())
                self.process.stdin.flush()
                time.sleep(0.1)
                self.lsp_client.exit()
                self.process.stdin.write(self.lsp_client.send())
                self.process.stdin.flush()
                time.sleep(0.1)
            except (IOError, BrokenPipeError) as e:
                self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()


class BaseConfig:
    def get_launch_commands(self) -> list[str]:
        pass

    def get_cfg(self) -> list[str]:
        pass

    def on_pre_init(self, project_path):
        pass


class ClangdConfig(BaseConfig):
    def get_launch_commands(self) -> list[str]:
        return ["clangd", "-log=verbose", "--background-index"]

    def get_cfg(self, project_path) -> list[str]:
        with open(Path(project_path) / "compile_commands.json", "r") as f:
            return json.load(f)

    def on_pre_init(self, project_path):
        if not (Path(project_path) / "compile_commands.json").exists():
            log("No compile commands found, will use default clangd config")
            # TODO: Implement default clangd config
            pass


class LspSession:
    def __init__(self, project_path: str, config):
        self.project_path = Path(project_path)
        self.config = config

        config.on_pre_init(self.project_path)
        launch_commands = config.get_launch_commands()

        self.runner = ClangdProcess(project_path, lsp.LspSession(launch_commands))
        self.runner.__enter__()
        self.config.on_post_init(self.project_path)
