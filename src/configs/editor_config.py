from dataclasses import dataclass, field


@dataclass
class EditorColors:
    background: str = "#272822"
    foreground: str = "#f8f8f2"
    current_line: str = "#3e3d32"
    line_numbers_bg: str = "#3e3d32"
    line_numbers_fg: str = "#75715e"
    selection: str = "#49483e"


@dataclass
class EditorConfig:
    colors: EditorColors = field(default_factory=EditorColors)
    font_family: str = "JetBrainsMono Nerd Font"
    font_size: int = 12
    tab_width: int = 4
    style_name: str = "monokai"
