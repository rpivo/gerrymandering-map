"""Fail when any Python function is longer than the repo's 100-line limit.

Usage: python tools/check_function_length.py PATH [PATH ...]

A function's length runs from its `def` line to its last line, so docstrings and
comments count. Nested functions are also checked on their own.
"""

import ast
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

MAX_LINES = 100
SKIP_DIRS = {".venv", "node_modules", "__pycache__", ".git"}


@dataclass(frozen=True)
class LongFunction:
    """A function that exceeds the line limit."""

    path: str
    name: str
    lineno: int
    length: int


def _walk_functions(
    node: ast.AST, prefix: str = ""
) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Yield (qualified name, node) for every function, including methods and nested ones."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            name = f"{prefix}{child.name}"
            yield name, child
            yield from _walk_functions(child, f"{name}.")
        elif isinstance(child, ast.ClassDef):
            yield from _walk_functions(child, f"{prefix}{child.name}.")
        else:
            yield from _walk_functions(child, prefix)


def find_long_functions(source: str, path: str, max_lines: int = MAX_LINES) -> list[LongFunction]:
    """Return every function in source that spans more than max_lines lines.

    Raises:
        SyntaxError: if source is not valid Python.
    """
    tree = ast.parse(source, filename=path)
    found = []
    for name, node in _walk_functions(tree):
        length = (node.end_lineno or node.lineno) - node.lineno + 1
        if length > max_lines:
            found.append(LongFunction(path, name, node.lineno, length))
    return found


def _python_files(paths: list[str]) -> Iterator[Path]:
    """Yield .py files under paths, skipping virtualenvs and caches."""
    for root in map(Path, paths):
        candidates = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for file in candidates:
            if not SKIP_DIRS.intersection(file.parts):
                yield file


def main(argv: list[str]) -> int:
    """Check every .py file under the given paths. Returns the process exit code."""
    failed = False
    for file in _python_files(argv):
        try:
            long_functions = find_long_functions(file.read_text(), str(file))
        except SyntaxError as error:
            print(f"{file}: could not parse ({error.msg})")
            failed = True
            continue
        for fn in long_functions:
            print(f"{fn.path}:{fn.lineno} {fn.name} is {fn.length} lines (limit {MAX_LINES})")
            failed = True
    if failed:
        print("Break long functions into smaller named functions (see CLAUDE.md).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
