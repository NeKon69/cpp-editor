from pathlib import Path
from typing import Dict, Optional, List
import tempfile

from PyQt6.QtGui import QSyntaxHighlighter, QTextDocument, QTextCharFormat, QColor

from src.editor.preprocessor import CppPreprocessor
from src.common.vars import log

from tree_sitter import Language, Parser, Query, QueryCursor, Tree, Node
import tree_sitter_cpp
import traceback


class SmartHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: QTextDocument, project_path: Path):
        super().__init__(parent)
        self.project_path = project_path
        self.preprocessor = CppPreprocessor(project_path)

        self._language = Language(tree_sitter_cpp.language())
        self._parser = Parser(self._language)

        self._tree: Optional[Tree] = None
        self._query: Optional[Query] = None
        self._captures_by_line: Dict[int, List[dict]] = {}
        self._formats: Dict[str, QTextCharFormat] = {}
        self._original_line_start: int = 0

        self._build_formats()
        self._build_query()

    def _build_query(self):
        query_str = """
        ; Types - HIGHEST priority
        (primitive_type) @type
        (type_identifier) @type
        (auto) @type
        
        ; Namespace identifiers
        ((namespace_identifier) @namespace
         (#match? @namespace "^[a-z_]"))
        
        ((namespace_identifier) @type
         (#match? @type "^[A-Z]"))
        
        ; Qualified types (std::string, etc)
        (qualified_identifier
          name: (type_identifier) @qualified_type)
        
        ; Functions - BEFORE qualified_name to have priority
        (call_expression
          function: (qualified_identifier
            name: (identifier) @function))
        
        (call_expression
          function: (identifier) @function)
        
        (template_function
          name: (identifier) @function)
        
        (template_method
          name: (field_identifier) @function)
        
        (function_declarator
          declarator: (identifier) @function)
        
        (function_declarator
          declarator: (qualified_identifier
            name: (identifier) @function))
        
        (function_declarator
          declarator: (field_identifier) @function)
        
        ; Qualified names (after functions so functions take priority)
        (qualified_identifier
          name: (identifier) @qualified_name)
        
        ; Field members
        (field_expression 
          field: (field_identifier) @member)
        
        ; Built-in variables
        (this) @variable.builtin
        (true) @constant
        (false) @constant
        
        ; Strings
        (raw_string_literal) @string
        (string_literal) @string
        (char_literal) @string
        (number_literal) @number
        
        ; Comments
        (comment) @comment
        
        ; Preprocessor
        (preproc_directive) @preproc
        (preproc_include) @preproc
        (preproc_def) @preproc
        
        ; Operators
        (binary_expression
          operator: _ @operator)
        
        (unary_expression
          operator: _ @operator)
        
        ; Keywords
        [
          "catch"
          "class"
          "co_await"
          "co_return"
          "co_yield"
          "constexpr"
          "constinit"
          "consteval"
          "delete"
          "explicit"
          "final"
          "friend"
          "mutable"
          "namespace"
          "noexcept"
          "new"
          "override"
          "private"
          "protected"
          "public"
          "template"
          "throw"
          "try"
          "typename"
          "using"
          "concept"
          "requires"
          "virtual"
          "if"
          "else"
          "while"
          "for"
          "do"
          "return"
          "break"
          "continue"
          "switch"
          "case"
          "default"
          "goto"
          "struct"
          "enum"
          "union"
          "typedef"
          "static"
          "const"
          "inline"
          "sizeof"
          "operator"
          "nullptr"
        ] @keyword
        
        ; All identifiers as variables (LOWEST priority)
        (identifier) @variable
        """

        self._query = self._language.query(query_str)

    def _build_formats(self):
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#D946EF"))
        keyword_fmt.setFontWeight(600)
        self._formats["keyword"] = keyword_fmt

        type_fmt = QTextCharFormat()
        type_fmt.setForeground(QColor("#00F0FF"))
        type_fmt.setFontWeight(600)
        self._formats["type"] = type_fmt

        namespace_fmt = QTextCharFormat()
        namespace_fmt.setForeground(QColor("#00F0FF"))
        self._formats["namespace"] = namespace_fmt

        qualified_type_fmt = QTextCharFormat()
        qualified_type_fmt.setForeground(QColor("#00F0FF"))
        self._formats["qualified_type"] = qualified_type_fmt

        qualified_name_fmt = QTextCharFormat()
        qualified_name_fmt.setForeground(QColor("#FFFFFF"))
        self._formats["qualified_name"] = qualified_name_fmt

        function_fmt = QTextCharFormat()
        function_fmt.setForeground(QColor("#FFFF00"))
        function_fmt.setFontWeight(700)
        self._formats["function"] = function_fmt

        member_fmt = QTextCharFormat()
        member_fmt.setForeground(QColor("#FFFF00"))
        self._formats["member"] = member_fmt

        variable_fmt = QTextCharFormat()
        variable_fmt.setForeground(QColor("#FFFFFF"))
        self._formats["variable"] = variable_fmt

        variable_builtin_fmt = QTextCharFormat()
        variable_builtin_fmt.setForeground(QColor("#D946EF"))
        self._formats["variable.builtin"] = variable_builtin_fmt

        operator_fmt = QTextCharFormat()
        operator_fmt.setForeground(QColor("#D946EF"))
        self._formats["operator"] = operator_fmt

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#FF7A5C"))
        self._formats["string"] = string_fmt

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#7FFF00"))
        self._formats["number"] = number_fmt

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#888888"))
        comment_fmt.setFontItalic(True)
        self._formats["comment"] = comment_fmt

        constant_fmt = QTextCharFormat()
        constant_fmt.setForeground(QColor("#7FFF00"))
        self._formats["constant"] = constant_fmt

        preproc_fmt = QTextCharFormat()
        preproc_fmt.setForeground(QColor("#D946EF"))
        self._formats["preproc"] = preproc_fmt

    def preprocess_file(self, file_path: Path):
        try:
            log(f"Preprocessing {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            result = self.preprocessor.preprocess(file_path)

            if not result or not result.full_content:
                log("Preprocessor failed, using original content")
                self._prepare_tree_sitter(original_content)
                self._original_line_start = 0
            else:
                preprocessed = result.full_content
                self._original_line_start = result.header_line_count

                if self._original_line_start < 0:
                    log("Warning: header_line_count is negative, resetting to 0")
                    self._original_line_start = 0

                prep_lines = preprocessed.split("\n")
                empty_lines_at_start = 0
                for line in prep_lines:
                    if line.strip() == "":
                        empty_lines_at_start += 1
                    else:
                        break

                self._original_line_start += empty_lines_at_start

                log(
                    f"Preprocessed: {len(preprocessed)} bytes, header lines: {self._original_line_start}, empty lines at start: {empty_lines_at_start}"
                )
                self._prepare_tree_sitter(preprocessed)

            self._query_and_sort_captures()
            self.rehighlight()
            log("Highlighter updated successfully")

        except Exception as e:
            log(f"Error in preprocess_file: {e}")
            log(traceback.format_exc())

    def _prepare_tree_sitter(self, content: str):
        try:
            content_bytes = content.encode("utf-8")
            self._tree = self._parser.parse(content_bytes)
            log(f"Tree-sitter parsed successfully")
        except Exception as e:
            log(f"Error parsing with tree-sitter: {e}")
            self._tree = None

    def _query_and_sort_captures(self):
        if not self._tree or not self._query:
            log("No tree or query available")
            return

        try:
            self._captures_by_line.clear()

            cursor = QueryCursor(self._query)
            captures_dict = cursor.captures(self._tree.root_node)

            priority = {
                "type": 100,
                "namespace": 100,
                "qualified_type": 100,
                "function": 90,
                "member": 90,
                "variable.builtin": 80,
                "qualified_name": 80,
                "operator": 70,
                "variable": 70,
                "string": 60,
                "number": 60,
                "constant": 60,
                "preproc": 40,
                "comment": 50,
                "keyword": 40,
            }

            captures_by_pos: Dict[tuple, List[tuple]] = {}

            for capture_name, nodes in captures_dict.items():
                for node in nodes:
                    start_row = node.start_point[0]
                    start_col = node.start_point[1]
                    end_row = node.end_point[0]
                    end_col = node.end_point[1]

                    adjusted_row = start_row - self._original_line_start

                    if adjusted_row < 0:
                        log(
                            f"[SKIP] Row {start_row}: before header cutpoint (original_line_start={self._original_line_start})"
                        )
                        continue

                    length = (
                        end_col - start_col
                        if start_row == end_row
                        else len(node.text or b"")
                    )
                    node_text = (node.text or b"").decode("utf-8", errors="replace")

                    log(
                        f"[TOKEN] Line {adjusted_row+1}: '{node_text}' -> @{capture_name} @ col {start_col}-{end_col}"
                    )

                    pos_key = (adjusted_row, start_col, length)
                    if pos_key not in captures_by_pos:
                        captures_by_pos[pos_key] = []

                    captures_by_pos[pos_key].append(
                        (capture_name, priority.get(capture_name, 0))
                    )

            for (adjusted_row, start_col, length), captures in captures_by_pos.items():
                if adjusted_row not in self._captures_by_line:
                    self._captures_by_line[adjusted_row] = []

                best_capture = max(captures, key=lambda x: x[1])

                self._captures_by_line[adjusted_row].append(
                    {"name": best_capture[0], "start_col": start_col, "length": length}
                )

            log(
                f"Captured {sum(len(v) for v in self._captures_by_line.values())} elements across {len(self._captures_by_line)} lines, original_line_start={self._original_line_start}"
            )

        except Exception as e:
            log(f"Error in query_and_sort_captures: {e}")
            log(traceback.format_exc())

    def highlightBlock(self, text: str):
        try:
            block_number = self.currentBlock().blockNumber()

            if block_number not in self._captures_by_line:
                return

            captures = self._captures_by_line[block_number]

            for capture in captures:
                capture_name = capture["name"]
                start_col = capture["start_col"]
                length = capture["length"]

                if capture_name in self._formats:
                    self.setFormat(start_col, length, self._formats[capture_name])

        except Exception as e:
            log(f"Error in highlightBlock: {e}")

    def update_tree(self, content: str):
        try:
            log(f"update_tree called with {len(content)} bytes")

            if not self.preprocessor:
                self._prepare_tree_sitter(content)
                self._original_line_start = 0
                self._query_and_sort_captures()
                self.rehighlight()
                return

            try:
                project_tmp = self.project_path / ".highlight_tmp.cpp"
                project_tmp.write_text(content, encoding="utf-8")

                try:
                    result = self.preprocessor.preprocess(project_tmp)

                    if result and result.full_content:
                        preprocessed = result.full_content
                        self._original_line_start = result.header_line_count

                        if self._original_line_start < 0:
                            log(
                                "Warning: header_line_count is negative in update_tree, resetting to 0"
                            )
                            self._original_line_start = 0

                        prep_lines = preprocessed.split("\n")
                        empty_lines_at_start = 0
                        for line in prep_lines:
                            if line.strip() == "":
                                empty_lines_at_start += 1
                            else:
                                break

                        self._original_line_start += empty_lines_at_start

                        log(
                            f"Preprocessed in update_tree: {len(preprocessed)} bytes, header lines: {self._original_line_start}, empty lines at start: {empty_lines_at_start}"
                        )
                        self._prepare_tree_sitter(preprocessed)
                    else:
                        log("Preprocessor failed in update_tree, using original")
                        self._prepare_tree_sitter(content)
                        self._original_line_start = 0
                finally:
                    project_tmp.unlink(missing_ok=True)
            except Exception as e:
                log(f"Error preprocessing in update_tree: {e}")
                self._prepare_tree_sitter(content)
                self._original_line_start = 0

            self._query_and_sort_captures()
            self.rehighlight()
            log("update_tree completed successfully")

        except Exception as e:
            log(f"Error in update_tree: {e}")
            log(traceback.format_exc())
