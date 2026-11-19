"""Tests for the python-test-conventions pre-commit hook.

The hook compares a test file's staged content with its HEAD version, so the cases below feed
both sides of that comparison to `check`, and one end-to-end case runs `main` in a throwaway
git repository.

Run:
    pytest scripts/precommit/tests -v
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "python_test_conventions.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("python_test_conventions", HOOK)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hook = _load_hook()

_OVER = hook.MAX_TEST_MODULE_LINES + 5


def _module_with_lines(lines: int) -> str:
    body = "\n".join(f"VALUE_{index} = {index}" for index in range(lines - 1))
    return f"'''docstring'''\n{body}\n"


def test_check_reports_a_module_crossing_the_limit():
    problems = hook.check(Path("packages/x/tests/test_a.py"), _module_with_lines(_OVER), _module_with_lines(_OVER - 10))
    assert len(problems) == 1
    assert "split the module" in problems[0]


def test_check_lets_a_module_already_over_the_limit_grow():
    problems = hook.check(
        Path("packages/x/tests/test_a.py"), _module_with_lines(_OVER + 200), _module_with_lines(_OVER + 100)
    )
    assert problems == []


def test_check_reports_a_new_module_over_the_limit():
    problems = hook.check(Path("packages/x/tests/test_a.py"), _module_with_lines(_OVER), None)
    assert len(problems) == 1


def test_check_reports_an_autouse_fixture_added_to_a_conftest():
    staged = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef clear_caches():\n    yield\n"
    problems = hook.check(Path("services/web/server/tests/unit/with_dbs/conftest.py"), staged, "import pytest\n")
    assert len(problems) == 1
    assert "autouse fixture in a conftest" in problems[0]


def test_check_leaves_an_autouse_conftest_fixture_the_commit_did_not_touch():
    committed = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef clear_caches():\n    yield\n"
    problems = hook.check(Path("services/web/server/tests/unit/with_dbs/conftest.py"), committed + "\n", committed)
    assert problems == []


def test_check_allows_autouse_outside_a_conftest():
    staged = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef clear_caches():\n    yield\n"
    problems = hook.check(Path("packages/x/tests/test_a.py"), staged, None)
    assert problems == []


def test_check_reports_a_callback_fixture_that_is_not_named_create():
    staged = (
        "import pytest\n"
        "from collections.abc import Callable\n"
        "from typing import AsyncIterator\n\n\n"
        "@pytest.fixture\n"
        "def mocked_sizing() -> Callable[[], None]:\n    ...\n\n\n"
        "@pytest.fixture\n"
        "def create_project() -> Callable[[], None]:\n    ...\n\n\n"
        "@pytest.fixture\n"
        "def registered_user() -> AsyncIterator[dict]:\n    yield {}\n"
    )
    problems = hook.check(Path("packages/x/tests/test_a.py"), staged, None)
    assert len(problems) == 1
    assert "must be named create_*" in problems[0]


def test_check_reports_an_autouse_flag_added_to_an_existing_fixture():
    committed = "import pytest\n\n\n@pytest.fixture\ndef clear_caches():\n    yield\n"
    staged = "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef clear_caches():\n    yield\n"
    problems = hook.check(Path("packages/x/tests/conftest.py"), staged, committed)
    assert len(problems) == 1
    assert "autouse" in problems[0]


def test_fixtures_of_a_file_that_does_not_parse_are_ignored():
    assert hook.fixtures("def broken(:\n") == {}


def test_is_test_path_covers_test_modules_conftests_and_test_dirs():
    assert hook.is_test_path(Path("packages/x/tests/test_a.py"))
    assert hook.is_test_path(Path("services/web/server/tests/unit/with_dbs/conftest.py"))
    assert hook.is_test_path(Path("packages/x/test_a.py"))
    assert not hook.is_test_path(Path("packages/x/src/x/service.py"))


def _git(repo: Path, *args: str) -> None:
    subprocess.run(  # noqa: S603
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],  # noqa: S607
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_main_fails_on_a_staged_conftest_and_passes_once_it_is_fixed(tmp_path, monkeypatch, capsys):
    _git(tmp_path, "init", "--quiet")
    conftest = tmp_path / "tests" / "conftest.py"
    conftest.parent.mkdir()
    conftest.write_text("import pytest\n\n\n@pytest.fixture\ndef caches():\n    yield\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "--quiet", "-m", "init")
    monkeypatch.chdir(tmp_path)

    assert hook.main(["hook", "tests/conftest.py"]) == 0

    conftest.write_text(
        "import pytest\n\n\n@pytest.fixture(autouse=True)\ndef caches() -> int:\n    return 1\n",
        encoding="utf-8",
    )
    assert hook.main(["hook", "tests/conftest.py"]) == 1
    assert "autouse fixture in a conftest" in capsys.readouterr().out

    conftest.write_text("import pytest\n\n\n@pytest.fixture\ndef caches():\n    yield\n", encoding="utf-8")
    assert hook.main(["hook", "tests/conftest.py"]) == 0


def test_main_skips_files_outside_the_test_layout(tmp_path, monkeypatch):
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text(_module_with_lines(_OVER), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert hook.main(["hook", "src/service.py"]) == 0
