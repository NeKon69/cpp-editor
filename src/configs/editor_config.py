from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class EditorColors:
    background: str = "#1E1E1E"
    foreground: str = "#D4D4D4"
    current_line: str = "#2D2D30"
    line_numbers_bg: str = "#1E1E1E"
    line_numbers_fg: str = "#858585"

    keyword: str = "#D946EF"
    type_primitive: str = "#00F0FF"
    type_class: str = "#50FA7B"
    type_struct: str = "#50FA7B"
    type_enum: str = "#50FA7B"
    namespace: str = "#8BE9FD"
    function_call: str = "#FFFF00"
    function_definition: str = "#FFD700"
    member: str = "#FFFF00"
    variable: str = "#FFFFFF"
    variable_qualified: str = "#F8F8F2"
    variable_builtin: str = "#D946EF"
    operator: str = "#FF79C6"
    string: str = "#FF7A5C"
    number: str = "#BD93F9"
    comment: str = "#6272A4"
    constant_builtin: str = "#BD93F9"
    preproc: str = "#FF79C6"

    def to_dict(self) -> dict:
        return {
            "background": self.background,
            "foreground": self.foreground,
            "current_line": self.current_line,
            "line_numbers_bg": self.line_numbers_bg,
            "line_numbers_fg": self.line_numbers_fg,
            "keyword": self.keyword,
            "type_primitive": self.type_primitive,
            "type_class": self.type_class,
            "type_struct": self.type_struct,
            "type_enum": self.type_enum,
            "namespace": self.namespace,
            "function_call": self.function_call,
            "function_definition": self.function_definition,
            "member": self.member,
            "variable": self.variable,
            "variable_qualified": self.variable_qualified,
            "variable_builtin": self.variable_builtin,
            "operator": self.operator,
            "string": self.string,
            "number": self.number,
            "comment": self.comment,
            "constant_builtin": self.constant_builtin,
            "preproc": self.preproc,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class EditorConfig:
    font_family: str = "Fira Code"
    font_size: int = 11
    tab_width: int = 4
    colors: EditorColors = field(default_factory=EditorColors)
    active_theme: str = ""

    @classmethod
    def load(cls, global_db):
        font_family = global_db.get_setting("font_family") or "Fira Code"
        font_size = int(global_db.get_setting("font_size") or "11")
        tab_width = int(global_db.get_setting("tab_width") or "4")
        active_theme = global_db.get_setting("active_theme") or ""

        colors = EditorColors()
        if active_theme:
            theme_data = global_db.load_theme(active_theme)
            if theme_data:
                colors = EditorColors.from_dict(theme_data)

        return cls(
            font_family=font_family,
            font_size=font_size,
            tab_width=tab_width,
            colors=colors,
            active_theme=active_theme,
        )

    def save(self, global_db):
        try:
            global_db.set_setting("font_family", self.font_family)
            global_db.set_setting("font_size", str(self.font_size))
            global_db.set_setting("tab_width", str(self.tab_width))
            global_db.set_setting("active_theme", self.active_theme)
        except Exception as e:
            print(f"Failed to save config: {e}")
