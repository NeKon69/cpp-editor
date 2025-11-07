from pathlib import Path
from typing import List, Dict, Optional
import json
import platform
import shutil

from src.common.vars import log


class CMakeHelper:
    COMPILERS = {
        "gcc": {"windows": "mingw32-make", "linux": "gcc", "darwin": "gcc"},
        "clang": {"windows": "clang", "linux": "clang", "darwin": "clang"},
        "msvc": {"windows": "cl", "linux": None, "darwin": None},
    }

    def __init__(self, project_path: Path, compiler: str = "gcc"):
        self.project_path = project_path
        self.build_dir = project_path / "build"
        self.compile_commands_path = self.build_dir / "compile_commands.json"
        self.compiler = compiler
        self.system = platform.system().lower()
        if self.system == "darwin":
            self.system = "darwin"
        elif self.system == "windows":
            self.system = "windows"
        else:
            self.system = "linux"

    def get_cmake_generator(self) -> str:
        if self.compiler == "msvc":
            return "Visual Studio 16 2019"
        elif self.compiler == "gcc" and self.system == "windows":
            return "MinGW Makefiles"
        else:
            return "Unix Makefiles"

    def get_cmake_cxx_compiler(self) -> str:
        if self.compiler == "msvc":
            return "cl"
        elif self.compiler == "gcc":
            return "g++" if self.system != "windows" else "g++"
        elif self.compiler == "clang":
            return "clang++"
        return "c++"

    def get_preprocessor_cmd(self) -> str:
        if self.compiler == "msvc":
            return "cl"
        elif self.compiler == "gcc":
            return "gcc"
        else:
            return "clang"

    def check_compiler_available(self) -> bool:
        compiler_cmd = self.get_cmake_cxx_compiler()
        return shutil.which(compiler_cmd) is not None

    def get_include_dirs(self, file_path: Path) -> List[str]:
        if not self.compile_commands_path.exists():
            return [".", "include", "src"]

        try:
            with open(self.compile_commands_path) as f:
                commands = json.load(f)

            file_name = file_path.name
            file_path_str = str(file_path.resolve())

            for cmd in commands:
                cmd_file = cmd.get("file", "")
                if file_name in cmd_file or cmd_file.endswith(file_name):
                    args = cmd.get("arguments", [])
                    include_dirs = []

                    i = 0
                    while i < len(args):
                        if args[i] == "-I" and i + 1 < len(args):
                            include_dirs.append(args[i + 1])
                            i += 2
                        elif args[i].startswith("-I"):
                            include_dirs.append(args[i][2:])
                            i += 1
                        elif args[i] == "/I" and i + 1 < len(args):
                            include_dirs.append(args[i + 1])
                            i += 2
                        elif args[i].startswith("/I"):
                            include_dirs.append(args[i][2:])
                            i += 1
                        else:
                            i += 1

                    return include_dirs if include_dirs else [".", "include", "src"]

            return [".", "include", "src"]

        except Exception as e:
            log(f"failed to parse compile_commands.json: {e}")
            return [".", "include", "src"]

    def get_compile_flags(self, file_path: Path) -> List[str]:
        if not self.compile_commands_path.exists():
            return []

        try:
            with open(self.compile_commands_path) as f:
                commands = json.load(f)

            file_name = file_path.name
            for cmd in commands:
                if file_name in cmd.get("file", ""):
                    return cmd.get("arguments", [])

            return []

        except Exception as e:
            log(f"failed to parse compile_commands.json: {e}")
            return []
