from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Dict, Any


@dataclass
class EditorColors:
    background: str = "#272822"
    foreground: str = "#f8f8f2"
    current_line: str = "#3e3d32"
    line_numbers_bg: str = "#3e3d32"
    line_numbers_fg: str = "#75715e"
    selection: str = "#49483e"

    keyword: str = "#f92672"
    string: str = "#e6db74"
    comment: str = "#75715e"
    function: str = "#a6e22e"
    type_: str = "#66d9ef"
    number: str = "#ae81ff"
    operator: str = "#f92672"

    def to_dict(self) -> Dict[str, str]:
        return {
            "background": self.background,
            "foreground": self.foreground,
            "current_line": self.current_line,
            "line_numbers_bg": self.line_numbers_bg,
            "line_numbers_fg": self.line_numbers_fg,
            "selection": self.selection,
            "keyword": self.keyword,
            "string": self.string,
            "comment": self.comment,
            "function": self.function,
            "type_": self.type_,
            "number": self.number,
            "operator": self.operator,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]):
        return cls(**data)


@dataclass
class EditorConfig:
    colors: EditorColors = field(default_factory=EditorColors)
    font_family: str = "JetBrainsMono Nerd Font"
    font_size: int = 12
    tab_width: int = 4
    style_name: str = "monokai"
    config_path: Path = field(
        default_factory=lambda: Path.home() / ".cpp_editor_config.json"
    )

    def save(self):
        try:
            config_dict = {
                "colors": self.colors.to_dict(),
                "font_family": self.font_family,
                "font_size": self.font_size,
                "tab_width": self.tab_width,
                "style_name": self.style_name,
            }
            with open(self.config_path, "w") as f:
                json.dump(config_dict, f, indent=2)
        except Exception as e:
            print(f"failed to save config: {e}")

    @classmethod
    def load(cls):
        config_path = Path.home() / ".cpp_editor_config.json"
        if not config_path.exists():
            return cls()

        try:
            with open(config_path, "r") as f:
                data = json.load(f)

            colors_data = data.get("colors", {})
            colors = (
                EditorColors.from_dict(colors_data) if colors_data else EditorColors()
            )

            return cls(
                colors=colors,
                font_family=data.get("font_family", "JetBrainsMono Nerd Font"),
                font_size=data.get("font_size", 12),
                tab_width=data.get("tab_width", 4),
                style_name=data.get("style_name", "monokai"),
                config_path=config_path,
            )
        except Exception as e:
            print(f"failed to load config: {e}")
            return cls()
