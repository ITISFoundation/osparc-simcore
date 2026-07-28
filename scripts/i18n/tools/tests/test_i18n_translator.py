# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "litellm>=1.67.0",
#   "polib>=1.2.0",
#   "pytest>=8.0.0",
#   "typer>=0.12.0",
# ]
# ///
# ruff: noqa: SLF001
"""
tools/tests/test_i18n_translator.py

Unit tests for i18n_translator.py, focused on the redesigned change-detection and
snippet handling:

    - Re-translation triggers ONLY on untranslated msgstr or the `fuzzy` flag
      (both set by msgmerge exactly when the msgid changes). Line refs, comments,
      and header timestamps never trigger work.
    - Source snippets are read from the .pot for prompt context but NEVER written to
      the shipped .po (only CTX-INTERPRETATION survives).
    - Parallel execution is the default.

No real LLM is contacted: a fake provider (duck-typed `_generate_json`) is injected.

Run:
    uv run --with pytest --with litellm --with polib --with typer \
        pytest scripts/i18n/tools/tests/test_i18n_translator.py -v
"""

import importlib.util
import inspect
import json
import sys
import types
from pathlib import Path

import polib
import pytest
from typer.testing import CliRunner

TOOLS_DIR = Path(__file__).resolve().parent.parent


def _load_i18n_translator() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("i18n_translator", TOOLS_DIR / "i18n_translator.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tr = _load_i18n_translator()
runner = CliRunner()


class FakeProvider:
    """Duck-typed stand-in for LiteLLMProvider that records prompts and never calls an LLM."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _generate_json(self, prompt: str) -> dict[str, str]:
        self.calls.append(prompt)
        return {"interpretation": "note", "translation": "Hola"}


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def test_needs_translation_untranslated_is_true() -> None:
    assert tr._needs_translation(polib.POEntry(msgid="a", msgstr="")) is True


def test_needs_translation_fuzzy_is_true() -> None:
    assert tr._needs_translation(polib.POEntry(msgid="a", msgstr="b", flags=["fuzzy"])) is True


def test_needs_translation_translated_clean_is_false() -> None:
    assert tr._needs_translation(polib.POEntry(msgid="a", msgstr="b")) is False


def test_classify_entry_state_routes_new_updated_skipped() -> None:
    assert isinstance(tr._classify_entry_state(polib.POEntry(msgid="a", msgstr="")), tr.EntryNew)
    assert isinstance(tr._classify_entry_state(polib.POEntry(msgid="a", msgstr="b", flags=["fuzzy"])), tr.EntryUpdated)
    assert isinstance(tr._classify_entry_state(polib.POEntry(msgid="a", msgstr="b")), tr.EntrySkipped)


def test_is_untranslated_handles_plural_entries() -> None:
    empty_plural = polib.POEntry(msgid="a", msgid_plural="as", msgstr_plural={0: "", 1: ""})
    full_plural = polib.POEntry(msgid="a", msgid_plural="as", msgstr_plural={0: "x", 1: "y"})
    assert tr._is_untranslated(empty_plural) is True
    assert tr._is_untranslated(full_plural) is False


# ---------------------------------------------------------------------------
# Snippet handling / comment hygiene
# ---------------------------------------------------------------------------


def test_snippet_from_comment_reads_snippet_block_only() -> None:
    comment = "CTX-SNIPPET:\n  >>> foo()\n  bar()\nCTX-SNIPPET-VERSION: abc1234"
    assert tr._snippet_from_comment(comment) == ">>> foo()\nbar()"


def test_clean_tcomment_strips_snippet_and_version_keeps_interpretation() -> None:
    comment = (
        "CTX-SNIPPET:\n"
        "  >>> foo()\n"
        "CTX-SNIPPET-VERSION: abc1234\n"
        "CTX-INTERPRETATION: old note\n"
        "CTX-VERSION: abc1234 2026-01-01T00:00:00Z"
    )
    cleaned = tr._clean_tcomment(comment, None)
    assert cleaned == "CTX-INTERPRETATION: old note"
    assert "CTX-SNIPPET" not in cleaned
    assert "CTX-VERSION" not in cleaned


def test_clean_tcomment_overrides_interpretation_when_given() -> None:
    comment = "CTX-SNIPPET:\n  >>> foo()\nCTX-INTERPRETATION: old"
    assert tr._clean_tcomment(comment, "new note") == "CTX-INTERPRETATION: new note"


def test_clean_tcomment_preserves_non_ctx_passthrough() -> None:
    assert tr._clean_tcomment("some note\nCTX-SNIPPET:\n  code", None) == "some note"


def test_clean_tcomment_rejoins_wrapped_interpretation() -> None:
    # polib wraps a long CTX-INTERPRETATION across several '#' lines on save; on the next
    # load the continuation must be rejoined into the single line (not leak before it).
    wrapped = "CTX-INTERPRETATION: The string appears as a label,\nlikely a title,\nin the UI."
    cleaned = tr._clean_tcomment(wrapped, None)
    assert cleaned == "CTX-INTERPRETATION: The string appears as a label, likely a title, in the UI."
    # exactly one CTX-INTERPRETATION line, and nothing leaks before it
    assert cleaned.count("CTX-INTERPRETATION:") == 1
    assert cleaned.splitlines()[0].startswith("CTX-INTERPRETATION:")


# ---------------------------------------------------------------------------
# Placeholder protection / normalization / glossary
# ---------------------------------------------------------------------------


def test_protect_restore_roundtrip_preserves_placeholders() -> None:
    protected = tr._protect("Max {n} of %s items")
    assert "{n}" not in protected.text
    assert "%s" not in protected.text
    assert tr._restore(protected.text, protected.mapping) == "Max {n} of %s items"


def test_normalize_trailing_whitespace_matches_source_intent() -> None:
    assert tr._normalize_trailing_whitespace("Hello ", "Hola") == "Hola "
    assert tr._normalize_trailing_whitespace("Hello", "Hola  ") == "Hola"


def test_filter_glossary_keeps_only_relevant_terms() -> None:
    glossary = {"mesh": "malla", "solver": "solucionador"}
    assert tr._filter_glossary(glossary, "The mesh is fine", "") == {"mesh": "malla"}


def test_get_nplurals_reads_header_with_fallback() -> None:
    po = polib.POFile()
    po.metadata = {"Plural-Forms": "nplurals=3; plural=(n==1)?0:(n==2)?1:2;"}
    assert tr._get_nplurals(po) == 3
    assert tr._get_nplurals(polib.POFile()) == 2


# ---------------------------------------------------------------------------
# Job builder (with a fake provider)
# ---------------------------------------------------------------------------


def test_build_translation_job_translates_new_entry() -> None:
    fake = FakeProvider()
    entry = polib.POEntry(msgid="Hello", msgstr="")
    job = tr._build_translation_job(entry, fake, "Spanish", {}, {"Hello": ">>> user_message('Hello')"})
    assert isinstance(job, tr.TranslationCompleted)
    assert isinstance(job.state, tr.EntryNew)
    assert job.result.text == "Hola"
    assert len(fake.calls) == 1


def test_build_translation_job_skips_clean_entry_without_calling_llm() -> None:
    fake = FakeProvider()
    entry = polib.POEntry(msgid="Hi", msgstr="Hola")
    job = tr._build_translation_job(entry, fake, "Spanish", {}, {})
    assert isinstance(job, tr.TranslationSkipped)
    assert fake.calls == []


def test_build_translation_job_translates_fuzzy_as_updated() -> None:
    fake = FakeProvider()
    entry = polib.POEntry(msgid="Hi", msgstr="Hola", flags=["fuzzy"])
    job = tr._build_translation_job(entry, fake, "Spanish", {}, {})
    assert isinstance(job, tr.TranslationCompleted)
    assert isinstance(job.state, tr.EntryUpdated)


def test_build_translation_job_force_retranslates_clean_entry() -> None:
    fake = FakeProvider()
    entry = polib.POEntry(msgid="Hi", msgstr="Hola")
    job = tr._build_translation_job(entry, fake, "Spanish", {}, {}, force=True)
    assert isinstance(job, tr.TranslationCompleted)
    assert isinstance(job.state, tr.EntryUpdated)


# ---------------------------------------------------------------------------
# CLI defaults
# ---------------------------------------------------------------------------


def test_parallel_is_the_default_and_use_git_is_gone() -> None:
    sig = inspect.signature(tr.translate)
    assert sig.parameters["parallel"].default.default is True
    assert "use_git" not in sig.parameters


# ---------------------------------------------------------------------------
# End-to-end CLI: snippet stripping + change-detection idempotency
# ---------------------------------------------------------------------------


def _write_glossary(tmp_path: Path) -> Path:
    gloss = tmp_path / "glossary.json"
    gloss.write_text(json.dumps({"glossary": {"es_ES": {}}, "lang_names": {"es_ES": "Spanish"}}), encoding="utf-8")
    return gloss


def _write_pot_with_snippet(tmp_path: Path) -> Path:
    pot = tmp_path / "messages.pot"
    po = polib.POFile()
    po.metadata = {
        "Project-Id-Version": "osparc-simcore",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }
    po.append(
        polib.POEntry(
            msgid="Hello",
            msgstr="",
            tcomment='CTX-SNIPPET:\n  >>> user_message("Hello")\nCTX-SNIPPET-VERSION: abc1234',
        )
    )
    po.save(str(pot))
    return pot


def test_translate_cli_strips_snippet_and_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(tr, "LiteLLMProvider", lambda *_args, **_kwargs: fake)

    pot = _write_pot_with_snippet(tmp_path)
    gloss = _write_glossary(tmp_path)
    out = tmp_path / "es_ES.po"

    args = [
        "translate",
        "--pot",
        str(pot),
        "--lang",
        "es_ES",
        "--out",
        str(out),
        "--glossary",
        str(gloss),
        "--model",
        "openai/gpt-4o",
        "--no-progress",
    ]
    result = runner.invoke(tr.app, args, catch_exceptions=False)
    assert result.exit_code == 0, result.output

    catalog = polib.pofile(str(out))
    entry = catalog.find("Hello")
    assert entry is not None
    assert entry.msgstr == "Hola"
    # snippet must NOT leak into the shipped .po; only the interpretation survives
    assert "CTX-SNIPPET" not in (entry.tcomment or "")
    assert "CTX-INTERPRETATION: note" in (entry.tcomment or "")
    assert len(fake.calls) == 1

    # Second run over the produced .po: entry is translated and not fuzzy -> skipped,
    # so the LLM is never called again (only msgid/fuzzy changes trigger work).
    fake.calls.clear()
    args_rerun = [
        "translate",
        "--pot",
        str(pot),
        "--in-po",
        str(out),
        "--lang",
        "es_ES",
        "--out",
        str(out),
        "--glossary",
        str(gloss),
        "--model",
        "openai/gpt-4o",
        "--no-progress",
    ]
    result2 = runner.invoke(tr.app, args_rerun, catch_exceptions=False)
    assert result2.exit_code == 0, result2.output
    assert fake.calls == []


def _base_translate_args(pot: Path, gloss: Path, out: Path, model: str) -> list[str]:
    return [
        "translate",
        "--pot",
        str(pot),
        "--lang",
        "es_ES",
        "--out",
        str(out),
        "--glossary",
        str(gloss),
        "--model",
        model,
        "--no-progress",
    ]


def test_translate_cli_prints_plan_banner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(tr, "LiteLLMProvider", lambda *_args, **_kwargs: fake)

    pot = _write_pot_with_snippet(tmp_path)  # single untranslated entry
    gloss = _write_glossary(tmp_path)
    out = tmp_path / "es_ES.po"

    result = runner.invoke(tr.app, _base_translate_args(pot, gloss, out, "openai/gpt-4o"), catch_exceptions=False)
    assert result.exit_code == 0, result.output
    # Pre-flight scope: 1 untranslated entry -> 1 NEW / 0 UPDATE / 0 SKIP -> 1 to model
    assert "[plan]" in result.output
    assert "1 NEW" in result.output
    assert "to model" in result.output


def test_ollama_parallel_emits_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(tr, "LiteLLMProvider", lambda *_args, **_kwargs: fake)

    pot = _write_pot_with_snippet(tmp_path)
    gloss = _write_glossary(tmp_path)
    out = tmp_path / "es_ES.po"

    # Default parallel=True + default max-workers=4 => Ollama warning must fire.
    result = runner.invoke(tr.app, _base_translate_args(pot, gloss, out, "ollama/llama3.1"), catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "Ollama runs one local model instance" in result.output


def test_non_ollama_no_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(tr, "LiteLLMProvider", lambda *_args, **_kwargs: fake)

    pot = _write_pot_with_snippet(tmp_path)
    gloss = _write_glossary(tmp_path)
    out = tmp_path / "es_ES.po"

    result = runner.invoke(tr.app, _base_translate_args(pot, gloss, out, "openai/gpt-4o"), catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "Ollama runs one local model instance" not in result.output


def test_translate_cli_stamps_model_and_date_in_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeProvider()
    monkeypatch.setattr(tr, "LiteLLMProvider", lambda *_args, **_kwargs: fake)

    pot = _write_pot_with_snippet(tmp_path)
    gloss = _write_glossary(tmp_path)
    out = tmp_path / "es_ES.po"

    result = runner.invoke(tr.app, _base_translate_args(pot, gloss, out, "openai/gpt-4o"), catch_exceptions=False)
    assert result.exit_code == 0, result.output

    metadata = polib.pofile(str(out)).metadata
    assert metadata["X-Translation-Model"] == "openai/gpt-4o"
    # ISO-8601 UTC stamp, e.g. 2026-07-28T10:15:30Z
    assert metadata["X-Translation-Date"].endswith("Z")
    assert metadata["X-Translation-Date"][:4].isdigit()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
