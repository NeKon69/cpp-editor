from pathlib import Path
from typing import Optional, NamedTuple
import subprocess
import tempfile
import re
import hashlib
import json
import traceback

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
        log(
            f"preprocessor: instance created (project={project_path}, compiler={compiler})"
        )

    def preprocess(
        self,
        file_path: Path,
    ) -> Optional[PreprocessingResult]:
        log(
            f"preprocessor: ========== STARTING PREPROCESS FOR {file_path.name} =========="
        )
        try:
            file_mtime = file_path.stat().st_mtime
            log(f"preprocessor: file mtime={file_mtime}")

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            log(f"preprocessor: file read: {len(content)} bytes")

            directive_hash = self._hash_preprocessor_directives(content)
            cache_key = f"{file_path}:{file_mtime}:{directive_hash}"
            log(f"preprocessor: cache key: {cache_key}")

            old_directive_hash = self._directive_hashes.get(str(file_path))
            log(
                f"preprocessor: old directive hash: {old_directive_hash}, new: {directive_hash}"
            )

            if old_directive_hash and old_directive_hash == directive_hash:
                log("preprocessor: directives unchanged, checking cache")
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
                    log(f"preprocessor: using cached result (directives unchanged)")
                    return self._cache[old_cache_key]

            if cache_key in self._cache:
                log("preprocessor: using cached result (full key match)")
                return self._cache[cache_key]

            if old_directive_hash and old_directive_hash != directive_hash:
                log("preprocessor: directives changed, invalidating old cache entries")
                keys_to_remove = [
                    k for k in self._cache if k.startswith(f"{file_path}:")
                ]
                for k in keys_to_remove:
                    del self._cache[k]
                log(f"preprocessor: removed {len(keys_to_remove)} old cache entries")

            log("preprocessor: cache miss, running preprocessor...")
            preprocessed = self._run_preprocessor(file_path)
            if not preprocessed:
                log("preprocessor: ERROR - _run_preprocessor returned empty")
                log("preprocessor: ========== PREPROCESS FAILED ==========")
                return None

            log(f"preprocessor: preprocessor output: {len(preprocessed)} bytes")

            cut_point = self._find_cut_point(preprocessed, file_path)
            if cut_point == -1:
                log("preprocessor: ERROR - cut point not found")
                log("preprocessor: ========== PREPROCESS FAILED ==========")
                return None

            log(f"preprocessor: cut point found at line {cut_point}")

            header = self._extract_clean_header(preprocessed, cut_point)
            log(f"preprocessor: header extracted: {len(header)} bytes")

            final_content = header + "\n" + content
            header_line_count = header.count("\n") + 1 if header else 0
            log(
                f"preprocessor: final content: {len(final_content)} bytes, header_line_count={header_line_count}"
            )

            result = PreprocessingResult(
                full_content=final_content, header_line_count=header_line_count
            )

            self._cache[cache_key] = result
            self._directive_hashes[str(file_path)] = directive_hash
            log(f"preprocessor: result cached")

            log("preprocessor: ========== PREPROCESS COMPLETE ==========")
            return result

        except Exception as e:
            log(f"preprocessor: ERROR: {e}\n{traceback.format_exc()}")
            log("preprocessor: ========== PREPROCESS FAILED ==========")
            return None

    def _hash_preprocessor_directives(self, content: str) -> str:
        log("preprocessor: hashing preprocessor directives")
        directive_pattern = re.compile(
            r"^\s*#\s*(include|define|undef|ifdef|ifndef|if|elif|else|endif|pragma|error|warning|line)\b.*$",
            re.MULTILINE,
        )
        directives = directive_pattern.findall(content)
        log(f"preprocessor: found {len(directives)} preprocessor directives")
        directive_string = "\n".join(directives)
        h = hashlib.md5(directive_string.encode("utf-8")).hexdigest()
        log(f"preprocessor: directive hash: {h}")
        return h

    def _run_preprocessor(self, file_path: Path) -> Optional[str]:
        log(f"preprocessor: running external preprocessor (compiler={self.compiler})")
        tmp_output_path = (
            Path(tempfile.gettempdir()) / f"cpp_preproc_{file_path.name}.tmp"
        )

        try:
            include_dirs = self._get_include_dirs(file_path)
            log(f"preprocessor: include dirs: {include_dirs}")

            cmd = [self.compiler, "-E", "-x", "c++"]
            for inc_dir in include_dirs:
                cmd.append(f"-I{inc_dir}")
            cmd.extend([str(file_path), "-o", str(tmp_output_path)])
            log(f"preprocessor: executing: {' '.join(cmd)}")

            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.project_path, timeout=15
            )
            log(f"preprocessor: subprocess returned code {result.returncode}")

            if result.returncode != 0:
                log(f"preprocessor: ERROR - subprocess failed")
                log(f"preprocessor: stderr: {result.stderr[:500]}")
                log(f"preprocessor: stdout: {result.stdout[:500]}")
                return None

            if not tmp_output_path.exists():
                log(f"preprocessor: ERROR - output file not created")
                return None

            log(f"preprocessor: output file created successfully")
            with open(tmp_output_path, "r", encoding="utf-8", errors="ignore") as f:
                output = f.read()
            log(f"preprocessor: read output: {len(output)} bytes")
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
        log(
            f"preprocessor: reverse-searching for cut point for '{file_name}' in {len(lines)} lines"
        )

        pattern_flag2 = re.compile(rf'^#\s+\d+\s+".*{re.escape(file_name)}"\s+2')
        for i in range(len(lines) - 1, -1, -1):
            if pattern_flag2.match(lines[i]):
                log(
                    f"preprocessor: found LAST cut marker (flag 2) at line {i}: {lines[i][:80]}"
                )
                return i

        log("preprocessor: marker with flag 2 not found, trying without flag (reverse)")
        pattern_no_flag = re.compile(rf'^#\s+\d+\s+".*{re.escape(file_name)}"')
        for i in range(len(lines) - 1, -1, -1):
            if pattern_no_flag.match(lines[i]):
                log(
                    f"preprocessor: found LAST marker (no flag) at line {i}: {lines[i][:80]}"
                )
                return i

        log("preprocessor: ERROR - no cut point markers found (even in reverse scan)")
        return -1

    def _extract_clean_header(self, preprocessed: str, cut_point: int) -> str:
        log(f"preprocessor: extracting clean header up to line {cut_point}")
        lines = preprocessed.split("\n")
        log(f"preprocessor: total lines in preprocessed output: {len(lines)}")

        header_lines = lines[:cut_point]
        log(f"preprocessor: header_lines (raw): {len(header_lines)} lines")

        line_marker_pattern = re.compile(r'^#\s+\d+\s+".*"')
        clean_lines = [
            line for line in header_lines if not line_marker_pattern.match(line)
        ]
        log(
            f"preprocessor: clean_lines after filtering markers: {len(clean_lines)} lines"
        )

        if clean_lines:
            log(f"preprocessor: FIRST 3 clean lines: {clean_lines[:3]}")
            log(f"preprocessor: LAST 3 clean lines: {clean_lines[-3:]}")

        result = "\n".join(clean_lines)
        result_line_count = result.count("\n") + 1 if result else 0
        log(
            f"preprocessor: result string: {len(result)} bytes, {result_line_count} lines when split by newline"
        )

        return result

    def _get_include_dirs(self, file_path: Path) -> list:
        log("preprocessor: determining include directories")
        try:
            compile_commands_path = (
                self.project_path / "build" / "compile_commands.json"
            )
            log(f"preprocessor: looking for {compile_commands_path}")

            if not compile_commands_path.exists():
                log("preprocessor: compile_commands.json not found, using defaults")
                return [".", "include", "src"]

            with open(compile_commands_path) as f:
                commands = json.load(f)
            log(
                f"preprocessor: loaded {len(commands)} entries from compile_commands.json"
            )

            file_abs_path = str(file_path.resolve())
            for cmd in commands:
                cmd_file_path = str(
                    Path(cmd.get("directory", "."), cmd.get("file", "")).resolve()
                )
                if cmd_file_path == file_abs_path:
                    args = cmd.get("arguments", [])
                    include_dirs = []
                    i = 0
                    while i < len(args):
                        arg = args[i]
                        if arg == "-I" and i + 1 < len(args):
                            include_dirs.append(args[i + 1])
                            i += 2
                        elif arg.startswith("-I"):
                            include_dirs.append(arg[2:])
                            i += 1
                        else:
                            i += 1

                    if include_dirs:
                        log(
                            f"preprocessor: found {len(include_dirs)} include dirs from compile_commands.json"
                        )
                        return include_dirs

            log("preprocessor: no entry found in compile_commands.json, using defaults")
            return [".", "include", "src"]
        except Exception as e:
            log(f"preprocessor: ERROR getting include dirs: {e}, using defaults")
            return [".", "include", "src"]
