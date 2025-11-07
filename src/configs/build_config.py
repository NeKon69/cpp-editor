from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class BuildConfig:
    compiler: str = "gcc"
    config_mode: str = "custom"
    build_command: str = "cmake -B build && cmake --build build"
    run_command: str = "./build/app"
    config_path: Path = field(
        default_factory=lambda: Path.home() / ".cpp_editor_build.json"
    )

    def save(self):
        try:
            config_dict = {
                "compiler": self.compiler,
                "config_mode": self.config_mode,
                "build_command": self.build_command,
                "run_command": self.run_command,
            }
            with open(self.config_path, "w") as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            print(f"failed to save build config: {e}")

    @classmethod
    def load(cls):
        config_path = Path.home() / ".cpp_editor_build.json"
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            return cls(
                compiler=data.get("compiler", "gcc"),
                config_mode=data.get("config_mode", "custom"),
                build_command=data.get(
                    "build_command", "cmake -B build && cmake --build build"
                ),
                run_command=data.get("run_command", "./build/app"),
                config_path=config_path,
            )
        except Exception as e:
            print(f"failed to load build config: {e}")
            return cls()
