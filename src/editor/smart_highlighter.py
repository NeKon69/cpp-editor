from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
import traceback

from PyQt6.QtGui import QSyntaxHighlighter, QTextDocument, QTextCharFormat, QColor
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from src.editor.preprocessor import CppPreprocessor
from src.common.vars import log

from tree_sitter import Language, Parser, QueryCursor, Tree
import tree_sitter_cpp


def timestamp():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


class PreprocessWorker(QObject):
    finished = pyqtSignal(str, int, int)

    def __init__(self, preprocessor, file_path: Path):
        super().__init__()
        self.preprocessor = preprocessor
        self.file_path = file_path
        self.operation_id = 0

    def run(self):
        try:
            result = self.preprocessor.preprocess(self.file_path)

            if not result or not result.full_content:
                log(f"[{timestamp()}] PreprocessWorker: no result")
                self.finished.emit("", 0, self.operation_id)
                return

            header_line_count: int = result.header_line_count
            full_lines = result.full_content.split("\n")

            if header_line_count > 0 and header_line_count < len(full_lines):
                clean_header_lines = full_lines[:header_line_count]
                clean_header = "\n".join(clean_header_lines)
            else:
                clean_header = ""

            self.finished.emit(clean_header, header_line_count, self.operation_id)

        except Exception as e:
            log(f"[{timestamp()}] PreprocessWorker error: {e}")
            log(traceback.format_exc())
            self.finished.emit("", 0, self.operation_id)


class TreeSitterWorker(QObject):
    finished = pyqtSignal(object, dict, int, int)

    def __init__(self):
        super().__init__()
        self.content = None
        self.original_line_start = 0
        self.operation_id = 0

        self._language = Language(tree_sitter_cpp.language())
        self._parser = Parser(self._language)
        self._query = None
        self._build_query()

    def _build_query(self):
        query_str = """
    (primitive_type) @type.primitive
    (auto) @keyword.auto
    
    ; User-defined types
    (type_identifier) @type.class
    
    ; Template types
    (template_type
      name: (type_identifier) @type.class)
    
    ; Class/struct declarations
    (class_specifier
      name: (type_identifier) @type.class)
    
    (struct_specifier
      name: (type_identifier) @type.struct)
    
    (enum_specifier
      name: (type_identifier) @type.enum)
    
    ; Namespaces
    (namespace_identifier) @namespace
    
    ; Qualified identifiers
    (qualified_identifier
      scope: (namespace_identifier) @namespace
      name: (type_identifier) @type.class)
    
    (qualified_identifier
      scope: (namespace_identifier) @namespace)
    
    ; Function calls
    (call_expression
      function: (qualified_identifier
        name: (identifier) @function.call))
    
    (call_expression
      function: (identifier) @function.call)
    
    (call_expression
      function: (field_expression
        field: (field_identifier) @function.call))
    
    ; Function declarations
    (function_declarator
      declarator: (identifier) @function.definition)
    
    (function_declarator
      declarator: (qualified_identifier
        name: (identifier) @function.definition))
    
    (function_declarator
      declarator: (field_identifier) @function.definition)
    
    ; Template functions
    (template_function
      name: (identifier) @function.definition)
    
    (template_method
      name: (field_identifier) @function.definition)
    
    ; Member access
    (field_expression 
      field: (field_identifier) @member)
    
    ; Qualified names
    (qualified_identifier
      name: (identifier) @variable.qualified)
    
    ; Special identifiers
    (this) @variable.builtin
    (true) @constant.builtin
    (false) @constant.builtin
    
    ; nullptr as identifier
    ((identifier) @constant.builtin
     (#eq? @constant.builtin "nullptr"))
    
    ; Literals
    (string_literal) @string
    (raw_string_literal) @string
    (char_literal) @string
    (number_literal) @number
    
    ; Comments
    (comment) @comment
    
    ; Preprocessor - only real nodes
    (preproc_include) @preproc
    (preproc_def) @preproc
    (preproc_function_def) @preproc
    (preproc_call) @preproc
    (preproc_if) @preproc
    (preproc_ifdef) @preproc
    (preproc_else) @preproc
    (preproc_elif) @preproc
    
    ; Operators
    (binary_expression
      operator: _ @operator)
    
    (unary_expression
      operator: _ @operator)
    
    (update_expression
      operator: _ @operator)
    
    ; Keywords
    [
      "catch"
      "decltype"
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
      "extern"
      "sizeof"
      "operator"
    ] @keyword
    
    ; Regular variables (LOWEST priority)
    (identifier) @variable
    """

        self._query = self._language.query(query_str)

    def run(self):
        try:
            content_bytes = self.content.encode("utf-8")
            tree = self._parser.parse(content_bytes)

            captures_by_line = self._query_and_sort_captures(tree)

            self.finished.emit(
                tree, captures_by_line, self.original_line_start, self.operation_id
            )
        except Exception as e:
            log(f"[{timestamp()}] TreeSitterWorker error: {e}")
            log(traceback.format_exc())
            self.finished.emit(None, {}, self.original_line_start, self.operation_id)

    def _query_and_sort_captures(self, tree):
        captures_by_line = {}

        try:
            cursor = QueryCursor(self._query)
            captures_dict = cursor.captures(tree.root_node)

            priority = {
                "type.class": 110,
                "type.struct": 110,
                "type.enum": 110,
                "type.primitive": 105,
                "namespace": 100,
                "function.call": 95,
                "function.definition": 95,
                "member": 90,
                "variable.builtin": 85,
                "variable.qualified": 80,
                "constant.builtin": 75,
                "keyword.auto": 70,
                "keyword.decltype": 70,
                "keyword": 70,
                "operator": 65,
                "variable": 60,
                "string": 55,
                "number": 55,
                "comment": 50,
                "preproc": 45,
            }

            captures_by_pos: Dict[tuple, List[tuple]] = {}

            for capture_name, nodes in captures_dict.items():
                for node in nodes:
                    start_row = node.start_point[0]
                    start_col = node.start_point[1]
                    end_row = node.end_point[0]
                    end_col = node.end_point[1]

                    adjusted_row = start_row - self.original_line_start

                    if adjusted_row < 0:
                        continue

                    length = (
                        end_col - start_col
                        if start_row == end_row
                        else len(node.text or b"")
                    )

                    pos_key = (adjusted_row, start_col, length)
                    if pos_key not in captures_by_pos:
                        captures_by_pos[pos_key] = []

                    captures_by_pos[pos_key].append(
                        (capture_name, priority.get(capture_name, 0))
                    )

            for (adjusted_row, start_col, length), captures in captures_by_pos.items():
                if adjusted_row not in captures_by_line:
                    captures_by_line[adjusted_row] = []

                best_capture = max(captures, key=lambda x: x[1])

                captures_by_line[adjusted_row].append(
                    {"name": best_capture[0], "start_col": start_col, "length": length}
                )

        except Exception as e:
            log(f"[{timestamp()}] Error in query_and_sort_captures: {e}")

        return captures_by_line


class SmartHighlighter(QSyntaxHighlighter):
    def __init__(self, parent: QTextDocument, project_path: Path):
        super().__init__(parent)
        self.project_path = project_path
        self.preprocessor = CppPreprocessor(project_path)

        self._tree: Optional[Tree] = None
        self._captures_by_line: Dict[int, List[dict]] = {}
        self._formats: Dict[str, QTextCharFormat] = {}
        self._original_line_start: int = 0

        self._preprocessed_header: str = ""
        self._file_path: Optional[Path] = None

        self._preprocess_worker = None
        self._preprocess_thread = None
        self._tree_worker = None
        self._tree_thread = None
        self._is_preprocessing = False
        self._is_tree_processing = False
        self._operation_counter = 0
        self._last_completed_operation = 0

        self._build_formats()

    def _build_formats(self):
        self._formats.clear()
        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#D946EF"))
        keyword_fmt.setFontWeight(600)
        self._formats["keyword"] = keyword_fmt
        self._formats["keyword.auto"] = keyword_fmt

        type_primitive_fmt = QTextCharFormat()
        type_primitive_fmt.setForeground(QColor("#00F0FF"))
        type_primitive_fmt.setFontWeight(600)
        self._formats["type.primitive"] = type_primitive_fmt

        type_class_fmt = QTextCharFormat()
        type_class_fmt.setForeground(QColor("#50FA7B"))
        type_class_fmt.setFontWeight(700)
        self._formats["type.class"] = type_class_fmt

        type_struct_fmt = QTextCharFormat()
        type_struct_fmt.setForeground(QColor("#50FA7B"))
        type_struct_fmt.setFontWeight(700)
        self._formats["type.struct"] = type_struct_fmt

        type_enum_fmt = QTextCharFormat()
        type_enum_fmt.setForeground(QColor("#50FA7B"))
        type_enum_fmt.setFontWeight(700)
        self._formats["type.enum"] = type_enum_fmt

        namespace_fmt = QTextCharFormat()
        namespace_fmt.setForeground(QColor("#8BE9FD"))
        namespace_fmt.setFontItalic(True)
        self._formats["namespace"] = namespace_fmt

        function_call_fmt = QTextCharFormat()
        function_call_fmt.setForeground(QColor("#FFFF00"))
        function_call_fmt.setFontWeight(700)
        self._formats["function.call"] = function_call_fmt

        function_def_fmt = QTextCharFormat()
        function_def_fmt.setForeground(QColor("#FFD700"))
        function_def_fmt.setFontWeight(700)
        self._formats["function.definition"] = function_def_fmt

        member_fmt = QTextCharFormat()
        member_fmt.setForeground(QColor("#FFFF00"))
        self._formats["member"] = member_fmt

        variable_fmt = QTextCharFormat()
        variable_fmt.setForeground(QColor("#FFFFFF"))
        self._formats["variable"] = variable_fmt

        variable_qualified_fmt = QTextCharFormat()
        variable_qualified_fmt.setForeground(QColor("#F8F8F2"))
        self._formats["variable.qualified"] = variable_qualified_fmt

        variable_builtin_fmt = QTextCharFormat()
        variable_builtin_fmt.setForeground(QColor("#D946EF"))
        self._formats["variable.builtin"] = variable_builtin_fmt

        operator_fmt = QTextCharFormat()
        operator_fmt.setForeground(QColor("#FF79C6"))
        self._formats["operator"] = operator_fmt

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#FF7A5C"))
        self._formats["string"] = string_fmt

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#BD93F9"))
        self._formats["number"] = number_fmt

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6272A4"))
        comment_fmt.setFontItalic(True)
        self._formats["comment"] = comment_fmt

        constant_builtin_fmt = QTextCharFormat()
        constant_builtin_fmt.setForeground(QColor("#BD93F9"))
        self._formats["constant.builtin"] = constant_builtin_fmt

        preproc_fmt = QTextCharFormat()
        preproc_fmt.setForeground(QColor("#FF79C6"))
        self._formats["preproc"] = preproc_fmt

    def update_colors(self, colors):
        self._build_formats()
        for name, fmt in self._formats.items():
            if hasattr(colors, name.replace(".", "_")):
                fmt.setForeground(QColor(getattr(colors, name.replace(".", "_"))))
        self.rehighlight()

    def preprocess_file(self, file_path: Path, reason: str = "unknown"):
        if self._is_preprocessing:
            return

        self._operation_counter += 1
        operation_id = self._operation_counter
        log(f"[{timestamp()}] TRIGGER_HEAVY reason={reason} id={operation_id}")

        self._is_preprocessing = True
        self._file_path = file_path

        self._preprocess_thread = QThread()
        self._preprocess_worker = PreprocessWorker(self.preprocessor, file_path)
        self._preprocess_worker.operation_id = operation_id
        self._preprocess_worker.moveToThread(self._preprocess_thread)

        self._preprocess_thread.started.connect(self._preprocess_worker.run)
        self._preprocess_worker.finished.connect(self._on_preprocess_finished)
        self._preprocess_worker.finished.connect(self._preprocess_thread.quit)
        self._preprocess_worker.finished.connect(self._preprocess_worker.deleteLater)
        self._preprocess_thread.finished.connect(self._preprocess_thread.deleteLater)

        self._preprocess_thread.start()

    def _on_preprocess_finished(
        self, preprocessed_header, header_line_count, operation_id
    ):
        self._is_preprocessing = False

        if self._last_completed_operation > operation_id:
            return

        self._preprocessed_header = preprocessed_header
        self._original_line_start = header_line_count

        with open(self._file_path, "r", encoding="utf-8") as f:
            file_content = f.read()

        if header_line_count > 0:
            full_content = self._preprocessed_header + "\n" + file_content
        else:
            full_content = file_content

        self._last_completed_operation = operation_id
        self._start_tree_sitter(full_content, operation_id)

    def _start_tree_sitter(self, content: str, parent_operation_id: int):
        if self._is_tree_processing:
            return

        operation_id = parent_operation_id

        self._is_tree_processing = True

        self._tree_thread = QThread()
        self._tree_worker = TreeSitterWorker()
        self._tree_worker.content = content
        self._tree_worker.original_line_start = self._original_line_start
        self._tree_worker.operation_id = operation_id
        self._tree_worker.moveToThread(self._tree_thread)

        self._tree_thread.started.connect(self._tree_worker.run)
        self._tree_worker.finished.connect(self._on_tree_finished)
        self._tree_worker.finished.connect(self._tree_thread.quit)
        self._tree_worker.finished.connect(self._tree_worker.deleteLater)
        self._tree_thread.finished.connect(self._tree_thread.deleteLater)

        self._tree_thread.start()

    def _on_tree_finished(
        self, tree, captures_by_line, original_line_start, operation_id
    ):
        self._is_tree_processing = False

        if tree is None:
            return

        if self._last_completed_operation > operation_id:
            return

        self._last_completed_operation = operation_id
        self._tree = tree
        self._captures_by_line = captures_by_line
        self._original_line_start = original_line_start

        self.rehighlight()

    def highlightBlock(self, text: str):
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

    def update_tree(self, content: str, reason: str = "light"):
        if self._is_tree_processing:
            return

        self._operation_counter += 1
        operation_id = self._operation_counter

        if self._original_line_start > 0 and self._preprocessed_header:
            full_content = self._preprocessed_header + "\n" + content
        else:
            full_content = content

        self._start_tree_sitter(full_content, operation_id)
