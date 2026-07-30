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


def test_snippet_bounds_covers_target_line() -> None:
    lines = ["def f():", "    a = 1", "    user_message('x')", "    b = 2", "    return b"]
    start, end = ix._snippet_bounds(lines, 3)
    assert start <= 2 <= end


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
