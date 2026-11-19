#!/usr/bin/env python3
"""Fail the commit when a test file introduces a convention this repo forbids.

Rules from .github/instructions/python-tests.instructions.md:
  - a test module is split before it grows past 1000 lines,
  - a conftest.py defines no autouse fixture,
  - a fixture handing a callback back is named create_*.

Only what this commit introduces is reported. pre-commit stashes unstaged edits, so the file
on disk is the staged content, and HEAD is the baseline: files already over the limit, and
fixtures already autouse or misnamed, stay untouched until someone edits them for real.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

MAX_TEST_MODULE_LINES = 1000
_TEST_DIR_NAMES = frozenset({"tests", "test"})
_FIXTURE_MODULES = frozenset({"pytest", "pytest_asyncio"})


def is_test_path(path: Path) -> bool:
    return path.name.startswith("test_") or path.name == "conftest.py" or bool(_TEST_DIR_NAMES.intersection(path.parts))


def head_content(path: Path) -> str | None:
    """The file as committed, or None when the commit adds it."""
    result = subprocess.run(  # noqa: S603
        ["git", "show", f"HEAD:{path.as_posix()}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _is_fixture_decorator(decorator: ast.expr) -> bool:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return (
        isinstance(target, ast.Attribute)
        and target.attr == "fixture"
        and isinstance(target.value, ast.Name)
        and target.value.id in _FIXTURE_MODULES
    )


def _is_autouse(decorator: ast.expr) -> bool:
    if not isinstance(decorator, ast.Call):
        return False
    return any(
        keyword.arg == "autouse" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True
        for keyword in decorator.keywords
    )


def _returns_callback(annotation: ast.expr | None) -> bool:
    target = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    name = target.attr if isinstance(target, ast.Attribute) else target.id if isinstance(target, ast.Name) else ""
    return name.endswith("Callable")


def fixtures(source: str) -> dict[str, tuple[bool, bool, int]]:
    """Fixture name to (autouse, hands a callback back, line number)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    found: dict[str, tuple[bool, bool, int]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        decorators = [decorator for decorator in node.decorator_list if _is_fixture_decorator(decorator)]
        if decorators:
            found[node.name] = (
                any(_is_autouse(decorator) for decorator in decorators),
                _returns_callback(node.returns),
                node.lineno,
            )
    return found


def check(path: Path, staged: str, committed: str | None) -> list[str]:
    problems: list[str] = []
    baseline = "" if committed is None else committed

    committed_lines = len(baseline.splitlines())
    staged_lines = len(staged.splitlines())
    if committed_lines <= MAX_TEST_MODULE_LINES < staged_lines:
        problems.append(
            f"{path}: {staged_lines} lines (it had {committed_lines}): "
            f"split the module rather than growing it past {MAX_TEST_MODULE_LINES}"
        )

    committed_fixtures = fixtures(baseline)
    for name, (autouse, hands_callback, lineno) in fixtures(staged).items():
        previous = committed_fixtures.get(name)
        if previous is not None and previous[:2] == (autouse, hands_callback):
            continue  # unchanged in this commit
        if autouse and path.name == "conftest.py":
            problems.append(f"{path}:{lineno}: autouse fixture in a conftest: request it by name where it is needed")
        if hands_callback and not name.startswith("create_"):
            problems.append(
                f"{path}:{lineno}: fixture returning a callback must be named create_*: it hides what it creates"
            )
    return problems


def main(argv: list[str]) -> int:
    failed = False
    for filename in argv[1:]:
        path = Path(filename)
        if not path.is_file() or not is_test_path(path):
            continue
        try:
            staged = path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            continue
        for problem in check(path, staged, head_content(path)):
            print(problem)  # noqa: T201
            failed = True
    return 1 if failed else os.EX_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
