from pathlib import Path
from typing import Optional, NamedTuple
import subprocess
import tempfile
import re
import hashlib
import json
import traceback
import shlex

from src.common.vars import log


class PreprocessingResult(NamedTuple):
    full_content: str
    header_line_count: int


class CppPreprocessor:
    def __init__(self, project_path: Path, compiler: str = "clang++"):
        self.project_path = project_path
        self.compiler = compiler
        self._cache = {}
        self._directive_hashes = {}

    def preprocess(
        self,
        file_path: Path,
    ) -> Optional[PreprocessingResult]:
        try:
            file_mtime = file_path.stat().st_mtime

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            directive_hash = self._hash_preprocessor_directives(content)
            cache_key = f"{file_path}:{file_mtime}:{directive_hash}"

            old_directive_hash = self._directive_hashes.get(str(file_path))

            if old_directive_hash and old_directive_hash == directive_hash:
                old_cache_key = next(
                    (
                        k
                        for k in self._cache
                        if k.startswith(f"{file_path}:")
                        and k.endswith(f":{directive_hash}")
                    ),
                    None,
                )
                if old_cache_key:
                    return self._cache[old_cache_key]

            if cache_key in self._cache:
                return self._cache[cache_key]

            if old_directive_hash and old_directive_hash != directive_hash:
                keys_to_remove = [
                    k for k in self._cache if k.startswith(f"{file_path}:")
                ]
                for k in keys_to_remove:
                    del self._cache[k]

            preprocessed = self._run_preprocessor(file_path)
            if not preprocessed:
                return None

            cut_point = self._find_cut_point(preprocessed, file_path)
            if cut_point == -1:
                return None

            header = self._extract_clean_header(preprocessed, cut_point)

            final_content = header + "\n" + content
            header_line_count = header.count("\n") + 1 if header else 0

            result = PreprocessingResult(
                full_content=final_content, header_line_count=header_line_count
            )

            self._cache[cache_key] = result
            self._directive_hashes[str(file_path)] = directive_hash

            return result

        except Exception as e:
            log(f"preprocessor: ERROR: {e}\n{traceback.format_exc()}")
            log("preprocessor: ========== PREPROCESS FAILED ==========")
            return None

    def _hash_preprocessor_directives(self, content: str) -> str:
        directive_pattern = re.compile(
            r"^\s*#\s*(include|define|undef|ifdef|ifndef|if|elif|else|endif|pragma|error|warning|line)\b.*$",
            re.MULTILINE,
        )
        directives = directive_pattern.findall(content)
        directive_string = "\n".join(directives)
        h = hashlib.md5(directive_string.encode("utf-8")).hexdigest()
        return h

    def _run_preprocessor(self, file_path: Path) -> Optional[str]:
        tmp_output_path = (
            Path(tempfile.gettempdir()) / f"cpp_preproc_{file_path.name}.tmp"
        )

        try:
            include_dirs = self._get_include_dirs(file_path)

            cmd = [self.compiler, "-E", "-x", "c++"]
            for inc_dir in include_dirs:
                cmd.append(f"-I{inc_dir}")
            cmd.extend([str(file_path), "-o", str(tmp_output_path)])

            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.project_path, timeout=15
            )

            if result.returncode != 0:
                log(f"preprocessor: ERROR - subprocess failed")
                log(f"preprocessor: stderr: {result.stderr[:500]}")
                log(f"preprocessor: stdout: {result.stdout[:500]}")
                return None

            if not tmp_output_path.exists():
                log(f"preprocessor: ERROR - output file not created")
                return None

            with open(tmp_output_path, "r", encoding="utf-8", errors="ignore") as f:
                output = f.read()
            return output

        except FileNotFoundError:
            log(f"preprocessor: ERROR - compiler '{self.compiler}' not found in PATH")
            return None
        except subprocess.TimeoutExpired:
            log(f"preprocessor: ERROR - subprocess timeout")
            return None
        except Exception as e:
            log(f"preprocessor: ERROR: {e}")
            return None
        finally:
            tmp_output_path.unlink(missing_ok=True)
            log(f"preprocessor: cleaned up temp file")

    def _find_cut_point(self, preprocessed: str, file_path: Path) -> int:
        lines = preprocessed.split("\n")
        file_name = file_path.name

        pattern_flag2 = re.compile(rf'^#\s+\d+\s+".*{re.escape(file_name)}"\s+2')
        for i in range(len(lines) - 1, -1, -1):
            if pattern_flag2.match(lines[i]):
                return i

        pattern_no_flag = re.compile(rf'^#\s+\d+\s+".*{re.escape(file_name)}"')
        for i in range(len(lines) - 1, -1, -1):
            if pattern_no_flag.match(lines[i]):
                return i

        log("preprocessor: ERROR - no cut point markers found (even in reverse scan)")
        return -1

    def _extract_clean_header(self, preprocessed: str, cut_point: int) -> str:
        lines = preprocessed.split("\n")

        header_lines = lines[:cut_point]

        line_marker_pattern = re.compile(r'^#\s+\d+\s+".*"')
        clean_lines = [
            line for line in header_lines if not line_marker_pattern.match(line)
        ]

        result = "\n".join(clean_lines)

        return result

    def _get_include_dirs(self, file_path: Path) -> list:
        try:
            compile_commands_path = self.project_path / "compile_commands.json"

            if not compile_commands_path.exists():
                return [".", "include", "src"]

            with open(compile_commands_path) as f:
                commands = json.load(f)

            file_abs_path = file_path.resolve()
            for cmd in commands:
                cmd_file_path = Path(
                    cmd.get("directory", ""), cmd.get("file", "")
                ).resolve()

                if cmd_file_path == file_abs_path:
                    args = cmd.get("arguments")
                    if args is None:
                        command_str = cmd.get("command")
                        if command_str:
                            args = shlex.split(command_str)
                        else:
                            continue

                    include_dirs = []
                    i = 0
                    while i < len(args):
                        arg = args[i]
                        if arg in ("-I", "-isystem") and i + 1 < len(args):
                            include_dirs.append(args[i + 1])
                            i += 2
                        elif arg.startswith("-I"):
                            include_dirs.append(arg[2:])
                            i += 1
                        elif arg.startswith("-isystem"):
                            include_dirs.append(arg[len("-isystem") :])
                            i += 1
                        else:
                            i += 1

                    if include_dirs:
                        return include_dirs

                    break

            return [".", "include", "src"]
        except Exception:
            return [".", "include", "src"]
