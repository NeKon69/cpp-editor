import json
from pathlib import Path
from src.common.vars import log
from src.configs.base_config import BaseConfig


class ClangdConfig(BaseConfig):
    def get_launch_commands(self) -> list[str]:
        return ["clangd", "-log=verbose", "--background-index"]

    def get_cfg(self, project_path) -> list[str]:
        compile_commands_path = Path(project_path) / "compile_commands.json"
        if compile_commands_path.exists():
            with open(compile_commands_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def on_pre_init(self, project_path):
        compile_commands_path = Path(project_path) / "compile_commands.json"
        if not compile_commands_path.exists():
            log("No compile_commands.json found, creating default one")
            default_config = [
                {
                    "directory": str(Path(project_path).resolve()),
                    "command": "clang++ -std=c++17 -Wall",
                    "file": "main.cpp",
                }
            ]
            with open(compile_commands_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
