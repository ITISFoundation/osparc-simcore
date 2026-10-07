# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "Babel>=2.12.0",
#   "Jinja2>=3.0.0",
#   "polib>=1.2.0",
#   "pytest>=8.0.0",
#   "rich>=13.0.0",
#   "typer>=0.12.0",
# ]
# ///
# ruff: noqa: SLF001
"""
tools/tests/test_i18n_extractor.py

Unit tests for i18n_extractor.py covering the extraction backends and the enrich
step. Notable post-redesign assertion: `enrich` writes CTX-SNIPPET (source context
for the LLM) but NO LONGER writes CTX-SNIPPET-VERSION (git-blame staleness was
removed).

xgettext-backed tests self-skip when the `xgettext` binary is unavailable; the
Babel/JSON/enrich/validation tests are pure-Python and always run.

Run:
    uv run --with pytest --with polib --with typer --with rich --with Babel --with Jinja2 \
        pytest scripts/i18n/tools/tests/test_i18n_extractor.py -v
"""

import importlib.util
import json
import subprocess
import sys
import types
from collections.abc import Callable
from pathlib import Path

import polib
import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent


def _load_i18n_extractor() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("i18n_extractor", TOOLS_DIR / "i18n_extractor.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ix = _load_i18n_extractor()


def _xgettext_available() -> bool:
    return subprocess.run(["which", "xgettext"], capture_output=True, check=False).returncode == 0  # noqa: S607


requires_xgettext = pytest.mark.skipif(not _xgettext_available(), reason="xgettext binary required")


@pytest.fixture
def make_cpp_files(tmp_path: Path) -> Callable[[str], tuple[Path, Path]]:
    def _make(test_relative_path: str) -> tuple[Path, Path]:
        production_file = tmp_path / "widget.cpp"
        test_file = tmp_path / test_relative_path
        test_file.parent.mkdir(parents=True, exist_ok=True)
        production_file.touch()
        test_file.touch()
        return production_file, test_file

    return _make


# ---------------------------------------------------------------------------
# f-string validation
# ---------------------------------------------------------------------------


def test_validate_rejects_fstring_in_user_message(tmp_path: Path) -> None:
    src = tmp_path / "bad.py"
    src.write_text('x = 1\nuser_message(f"Hi {x}")\n', encoding="utf-8")
    assert ix.validate_no_fstring_translations([src]) is False


def test_validate_accepts_plain_user_message(tmp_path: Path) -> None:
    src = tmp_path / "good.py"
    src.write_text('user_message("Hi there")\n', encoding="utf-8")
    assert ix.validate_no_fstring_translations([src]) is True


def test_collect_python_hints_reads_hint_kwarg(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    src.write_text('user_message("Msg", _hint="be gentle")\n', encoding="utf-8")
    assert ix.collect_python_hints([src]) == {"Msg": "be gentle"}


# ---------------------------------------------------------------------------
# Source discovery exclusions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "test_relative_path, exclude_pattern",
    [
        ("test_widget.cpp", "test_*.cpp"),
        ("test/widget.cpp", "test/*"),
        ("testsuite/widget.cpp", "testsuite/*.cpp"),
    ],
)
def test_collect_sources_excludes_test_paths(
    make_cpp_files: Callable[[str], tuple[Path, Path]],
    tmp_path: Path,
    test_relative_path: str,
    exclude_pattern: str,
) -> None:
    production_file, _ = make_cpp_files(test_relative_path)

    files = ix.collect_sources(tmp_path, ["cpp"], [exclude_pattern])

    assert files == [production_file]


def test_collect_sources_includes_test_files_without_exclusions(
    make_cpp_files: Callable[[str], tuple[Path, Path]],
    tmp_path: Path,
) -> None:
    production_file, test_file = make_cpp_files("test_widget.cpp")

    files = ix.collect_sources(tmp_path, ["cpp"])

    assert files == [test_file, production_file]


# ---------------------------------------------------------------------------
# JSON key extraction (guided tours)
# ---------------------------------------------------------------------------


def test_json_keys_extractor_extracts_only_listed_keys(tmp_path: Path) -> None:
    src_dir = tmp_path / "tours"
    src_dir.mkdir()
    (src_dir / "tour.json").write_text(
        json.dumps([{"id": "a", "name": "Welcome", "description": "Intro"}], indent=2),
        encoding="utf-8",
    )
    out_pot = tmp_path / "tours.pot"

    ok = ix.JsonKeysExtractor().run(src_dir, out_pot, {"name", "description"}, "*.json")
    assert ok is True

    msgids = {entry.msgid for entry in polib.pofile(str(out_pot))}
    assert "Welcome" in msgids
    assert "Intro" in msgids
    assert "a" not in msgids  # wiring key `id` must not be extracted


# ---------------------------------------------------------------------------
# Jinja2 (Babel) extraction
# ---------------------------------------------------------------------------


def test_babel_jinja_extractor_reads_trans_block(tmp_path: Path) -> None:
    src_dir = tmp_path / "templates"
    src_dir.mkdir()
    (src_dir / "email.j2").write_text("<p>{% trans %}Hello world{% endtrans %}</p>\n", encoding="utf-8")
    out_pot = tmp_path / "templates.pot"

    ok = ix.BabelJinjaExtractor().run(src_dir, out_pot)
    assert ok is True

    msgids = {entry.msgid for entry in polib.pofile(str(out_pot))}
    assert "Hello world" in msgids


# ---------------------------------------------------------------------------
# xgettext extraction
# ---------------------------------------------------------------------------


@requires_xgettext
def test_xgettext_extractor_reads_user_message(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    src.write_text('user_message("Extract me")\n', encoding="utf-8")
    out_pot = tmp_path / "messages.pot"

    ok = ix.XgetextExtractor().run([src], out_pot)
    assert ok is True

    msgids = {entry.msgid for entry in polib.pofile(str(out_pot))}
    assert "Extract me" in msgids


# ---------------------------------------------------------------------------
# xgettext wide-literal truncation workaround (_fold_wide_literal_runs)
# ---------------------------------------------------------------------------


def test_fold_strips_wide_from_continuations() -> None:
    text = 'tr(L"aaa " L"bbb " L"ccc");\n'
    folded, n = ix._fold_wide_literal_runs(text)
    assert n == 1
    assert folded == 'tr(L"aaa " "bbb " "ccc");\n'


def test_fold_moves_wide_prefix_to_first_fragment() -> None:
    text = 'tr("aaa " L"bbb");\n'
    folded, n = ix._fold_wide_literal_runs(text)
    assert n == 1
    assert folded == 'tr(L"aaa " "bbb");\n'


def test_fold_preserves_line_count() -> None:
    text = 'line0\nfoo(tr(L"a "\n    L"b "\n    L"c"));\nlast\n'
    folded, n = ix._fold_wide_literal_runs(text)
    assert n == 1
    assert folded.count("\n") == text.count("\n")
    assert folded == ('line0\nfoo(tr(L"a "\n    "b "\n    "c"));\nlast\n')


def test_fold_skips_mergeable_and_commented_runs() -> None:
    text = (
        'tr("n1 " "n2");\n'  # all-narrow: mergeable, leave alone
        'tr(L"w1 " "w2");\n'  # wide-first narrow-cont: mergeable, leave alone
        '// tr(L"c1 " L"c2")\n'  # inside a comment: not code
        '/* tr(L"d1 " L"d2") */\n'  # inside a block comment: not code
        'QT_TR_NOOP(L"q1 " L"q2");\n'  # flagged keyword: folds
    )
    folded, n = ix._fold_wide_literal_runs(text)
    assert n == 1
    assert 'tr("n1 " "n2")' in folded
    assert 'tr(L"w1 " "w2")' in folded
    assert 'tr(L"c1 " L"c2")' in folded  # comment untouched
    assert '/* tr(L"d1 " L"d2") */' in folded  # block comment untouched
    assert 'QT_TR_NOOP(L"q1 " "q2")' in folded


def test_fold_skips_non_l_wide_kinds() -> None:
    # u8/u/U runs cannot bind the tr() overloads; folding them could change the
    # literal TYPE, so they must be left unfolded (warn path).
    text = 'tr(L"a " u8"b");\n'
    folded, n = ix._fold_wide_literal_runs(text)
    assert n == 0
    assert folded == text


def test_fold_ignores_identifier_suffixed_literals() -> None:
    # the L of SOMETHING_L"..." is an identifier char, not a wide prefix
    text = 'auto s = SOMETHING_L"x"; tr(L"a " "b");\n'
    folded, n = ix._fold_wide_literal_runs(text)
    assert n == 0
    assert folded == text


@requires_xgettext
def test_xgettext_extractor_recovers_wide_split_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tr() whose message is split across wide literals must extract as ONE
    complete msgid (xgettext alone truncates it at the first wide continuation),
    and the #: reference must still point at the real file and line."""
    src_dir = tmp_path / "proj"
    src_dir.mkdir()
    src = src_dir / "wide.cpp"
    src.write_text(
        'void f() {\n    tr(L"part one " L"part two " L"part three");\n}\n',
        encoding="utf-8",
    )
    out_pot = tmp_path / "wide.pot"
    monkeypatch.chdir(tmp_path)

    ok = ix.XgetextExtractor().run([Path("proj/wide.cpp")], out_pot)
    assert ok is True

    entries = polib.pofile(str(out_pot))
    msgids = {e.msgid for e in entries}
    assert "part one part two part three" in msgids
    assert "part one " not in msgids  # the truncated shape must be gone
    entry = next(e for e in entries if e.msgid == "part one part two part three")
    assert ("proj/wide.cpp", "2") in entry.occurrences


# ---------------------------------------------------------------------------
# enrich — CTX-SNIPPET present, CTX-SNIPPET-VERSION removed
# ---------------------------------------------------------------------------


def test_enrich_writes_snippet_without_version(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "mod.py").write_text('import os\nuser_message("Hello")\n', encoding="utf-8")

    pot_path = tmp_path / "messages.pot"
    pot = polib.POFile()
    pot.metadata = {"Content-Type": "text/plain; charset=UTF-8"}
    pot.append(polib.POEntry(msgid="Hello", msgstr="", occurrences=[("src/mod.py", "2")]))
    pot.save(str(pot_path))

    ix.enrich(pot_path, tmp_path, py_hints={})

    entry = polib.pofile(str(pot_path)).find("Hello")
    assert entry is not None
    assert "CTX-SNIPPET:" in (entry.tcomment or "")
    assert 'user_message("Hello")' in (entry.tcomment or "")
    assert "CTX-SNIPPET-VERSION" not in (entry.tcomment or "")
    assert "CTX-VERSION" not in (entry.tcomment or "")


# ---------------------------------------------------------------------------
# CTX comment parse/render + snippet bounds
# ---------------------------------------------------------------------------


def test_parse_ctx_comment_splits_fields_and_snippet() -> None:
    comment = "CTX-SNIPPET:\n   >>> foo()\nCTX-INTERPRETATION: a note"
    passthrough, ctx_fields, snippet = ix.parse_ctx_comment(comment)
    assert ctx_fields.get("CTX-INTERPRETATION") == "a note"
    assert any("foo()" in line for line in snippet)
    assert passthrough == []


def test_snippet_bounds_expands_to_enclosing_block_and_stops_at_boundaries() -> None:
    # expands upward through the sibling header, stops at the shallower-indented line
    lines = ["def f():", "    if x:", "        user_message('x')", "    y = 1"]
    assert ix._snippet_bounds(lines, 3) == (1, 2)

    # blank lines are block boundaries (the blank line itself is still included)
    lines = ["", "    user_message('x')", "    b = 2", ""]
    assert ix._snippet_bounds(lines, 2) == (0, 2)

    # max_context clamps expansion in both directions
    lines = ["    a = 1", "    b = 2", "    user_message('x')", "    c = 3", "    d = 4"]
    assert ix._snippet_bounds(lines, 3, max_context=1) == (1, 3)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
