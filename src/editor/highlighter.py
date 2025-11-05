from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from pygments import lex
from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name
from pygments.token import Token

from src.common.vars import log


class PygmentsHighlighter(QSyntaxHighlighter):
    def __init__(
        self,
        parent: QTextDocument,
        lexer_name: str = "cpp",
        style_name: str = "monokai",
    ):
        super().__init__(parent)

        self._lexer = get_lexer_by_name(lexer_name)
        self._style = get_style_by_name(style_name)
        self._formats = {}

        self._build_formats()

    def _build_formats(self):
        """Build QTextCharFormat cache for each token type"""
        for token, style in self._style:
            fmt = QTextCharFormat()

            if style["color"]:
                fmt.setForeground(QColor(f"#{style['color']}"))

            if style["bgcolor"]:
                fmt.setBackground(QColor(f"#{style['bgcolor']}"))

            if style["bold"]:
                fmt.setFontWeight(700)

            if style["italic"]:
                fmt.setFontItalic(True)

            if style["underline"]:
                fmt.setFontUnderline(True)

            self._formats[token] = fmt

    def highlightBlock(self, text: str):
        """Highlight a single block of text"""
        try:
            tokens = list(lex(text, self._lexer))

            index = 0
            for token_type, value in tokens:
                length = len(value)
                fmt = self._get_format(token_type)

                if fmt:
                    self.setFormat(index, length, fmt)

                index += length

        except Exception as e:
            log(f"highlighting error: {e}")

    def _get_format(self, token_type) -> Optional[QTextCharFormat]:
        """Get format for token type with fallback to parent types"""
        while token_type:
            if token_type in self._formats:
                return self._formats[token_type]
            token_type = token_type.parent

        return None

    def set_style(self, style_name: str):
        """Change highlighting style"""
        self._style = get_style_by_name(style_name)
        self._formats.clear()
        self._build_formats()
        self.rehighlight()
