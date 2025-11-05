from typing import List, Dict, Any, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCompleter, QPlainTextEdit
from PyQt6.QtGui import QTextCursor
from src.common.vars import log


class LspCompleter(QCompleter):
    def __init__(self, editor: QPlainTextEdit):
        super().__init__(editor)
        self._editor = editor
        self._completions: List[Dict[str, Any]] = []
        self.activated[str].connect(self._on_activated)
        self.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.setMaxVisibleItems(12)
        print("[LspCompleter] Initialized")

    def update_completions(self, completions: List[Dict[str, Any]]):
        print(f"[LspCompleter] update_completions called with {len(completions)} items")

        if not completions:
            print("[LspCompleter] No completions, hiding popup")
            self.popup().hide()
            return

        self._completions = completions
        labels = [item.get("label", "") for item in completions]
        print(
            f"[LspCompleter] Labels: {labels[:5]}..."
            if len(labels) > 5
            else f"[LspCompleter] Labels: {labels}"
        )
        self.model().setStringList(labels)

        cursor = self._editor.textCursor()
        block_text = cursor.block().text()
        pos_in_block = cursor.positionInBlock()
        print(
            f"[LspCompleter] Cursor pos: line={cursor.blockNumber()}, pos_in_block={pos_in_block}"
        )
        print(f"[LspCompleter] Block text: '{block_text}'")

        prefix = self._extract_prefix(block_text, pos_in_block)
        print(f"[LspCompleter] Extracted prefix: '{prefix}'")
        self.setCompletionPrefix(prefix)

        cursor_rect = self._editor.cursorRect()
        print(f"[LspCompleter] Cursor rect: ({cursor_rect.x()}, {cursor_rect.y()})")
        self.complete(cursor_rect)
        print(f"[LspCompleter] Popup shown")

    def _extract_prefix(self, block_text: str, pos_in_block: int) -> str:
        if pos_in_block <= 0:
            return ""

        i = pos_in_block - 1
        while i >= 0:
            char = block_text[i]
            if char.isalnum() or char == "_":
                i -= 1
            elif i > 0 and block_text[i - 1 : i + 1] in ("->", "::"):
                i -= 2
            else:
                break

        start = i + 1
        result = block_text[start:pos_in_block]
        print(
            f"[LspCompleter._extract_prefix] block_text='{block_text}', pos={pos_in_block}, start={start}, prefix='{result}'"
        )
        return result

    def _on_activated(self, text: str):
        print(f"[LspCompleter._on_activated] Activated with text: '{text}'")
        try:
            cursor = self._editor.textCursor()
            block_text = cursor.block().text()
            pos_in_block = cursor.positionInBlock()
            print(
                f"[LspCompleter._on_activated] Before: block='{block_text}', pos={pos_in_block}"
            )

            prefix = self._extract_prefix(block_text, pos_in_block)
            print(f"[LspCompleter._on_activated] Deleting {len(prefix)} chars")

            for _ in range(len(prefix)):
                cursor.deletePreviousChar()

            print(f"[LspCompleter._on_activated] Inserting text: '{text}'")
            cursor.insertText(text)
            self._editor.setTextCursor(cursor)
            print(f"[LspCompleter._on_activated] Success")
        except Exception as e:
            log(f"Failed to insert completion: {e}")
            print(f"[LspCompleter._on_activated] ERROR: {e}")
