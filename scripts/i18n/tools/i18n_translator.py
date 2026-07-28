# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "litellm>=1.67.0",
#   "polib>=1.2.0",
#   "typer>=0.12.0",
# ]
# ///
# ruff: noqa: B008, FBT001, FBT003
"""
tools/i18n_translator.py
Translate a .pot/.po catalog using an LLM provider (litellm-backed).

Per entry:
    - Reads CTX-SNIPPET from the .pot for prompt context (never stored in the .po)
    - Includes extracted @TRANSLATOR notes, glossary terms, and source snippet in the prompt
    - LLM returns: context interpretation + translation
        - Writes back CTX-INTERPRETATION and msgstr
    - Translates in parallel by default with live progress and incremental atomic saves
    - Re-translates only entries that are untranslated or flagged fuzzy (msgid changed)

Commands:
  translate   Translate a .pot into a language-specific .po
  models      List the models litellm knows about, grouped by provider

Usage:
    uv run tools/i18n_translator.py translate \\
    --pot messages.pot --lang zh_CN \\
    --out locale/zh_CN/LC_MESSAGES/messages.po

Provider is selected via --model using litellm model naming:
  - Ollama:     ollama/llama3.1  (default)
  - Anthropic:  anthropic/claude-sonnet-4-6
  - OpenAI:     openai/gpt-4o
  - Custom URL: openai/my-model  +  --base-url http://host:8000/v1

See https://docs.litellm.ai/docs/providers for the full list.
Requires provider-specific API key env vars only when needed
(e.g. ANTHROPIC_API_KEY, OPENAI_API_KEY).
"""

import json
import logging
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Final, NamedTuple

import litellm
import polib
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

DEFAULT_GLOSSARY_FILE = "glossary.json"

# @TRANSLATOR marker: human note in source -> xgettext --add-comments -> #. line.
# Literal is duplicated in i18n_extractor.py (TRANSLATOR_TAG); keep in sync.
TRANSLATOR_TAG: Final = "@TRANSLATOR"

# --- Type aliases ----------------------------------------------------------
# Scalars end in `Str`; mapping aliases end in `Dict`.
type LangCodeStr = str  # e.g. "zh_CN"
type LangNameStr = str  # e.g. "Simplified Chinese"
type TermStr = str  # source term, e.g. "mesh"
type TranslationStr = str  # translated text
type PlaceholderTokenStr = str  # e.g. "⟨0⟩"

# term → target-language term, e.g. {"mesh": "网格"}
type TermGlossaryDict = dict[TermStr, TranslationStr]
# lang code → per-language glossary
type AllGlossariesDict = dict[LangCodeStr, TermGlossaryDict]
# lang code → human-readable language name
type LangNamesDict = dict[LangCodeStr, LangNameStr]
# placeholder token → original placeholder, e.g. {"⟨0⟩": "{min_size}"}
type PlaceholderMapDict = dict[PlaceholderTokenStr, str]

console = Console()
_PO_SAVE_LOCK = threading.Lock()


class GlossaryData(NamedTuple):
    glossaries: AllGlossariesDict
    lang_names: LangNamesDict


class ProtectedText(NamedTuple):
    text: str  # msgid with placeholders swapped for tokens
    mapping: PlaceholderMapDict


class Translation(NamedTuple):
    interpretation: str  # one-sentence context note
    text: TranslationStr
    text_plural: TranslationStr | None = None  # set only for plural (msgid_plural) entries


@dataclass(frozen=True)
class EntryNew:
    entry: polib.POEntry  # explicit branch for untranslated entries


@dataclass(frozen=True)
class EntryUpdated:
    entry: polib.POEntry  # explicit branch for stale translated entries


@dataclass(frozen=True)
class EntrySkipped:
    entry: polib.POEntry  # explicit branch for already-fresh translated entries


type EntryState = EntryNew | EntryUpdated | EntrySkipped


@dataclass(frozen=True)
class TranslationSkipped:
    entry: polib.POEntry  # explicit branch for skipped entries


@dataclass(frozen=True)
class TranslationFailed:
    entry: polib.POEntry  # explicit branch for translation errors
    error: str


@dataclass(frozen=True)
class TranslationCompleted:
    entry: polib.POEntry  # explicit branch for successful translations
    state: EntryState
    result: Translation


type TranslationJob = TranslationSkipped | TranslationFailed | TranslationCompleted


def _load_glossary(path: str) -> GlossaryData:
    """Load glossary and lang_names, validating that both share the same lang keys."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    glossaries: AllGlossariesDict = data.get("glossary", {})
    lang_names: LangNamesDict = data.get("lang_names", {})
    if set(glossaries) != set(lang_names):
        only_glossary = sorted(set(glossaries) - set(lang_names))
        only_names = sorted(set(lang_names) - set(glossaries))
        parts = []
        if only_glossary:
            parts.append(f"in glossary but missing from lang_names: {only_glossary}")
        if only_names:
            parts.append(f"in lang_names but missing from glossary: {only_names}")
        msg = f"Glossary/lang_names key mismatch in {path}: {'; '.join(parts)}"
        raise ValueError(msg)
    return GlossaryData(glossaries, lang_names)


# Placeholders like {min_size}, %s, or %(count)s must survive translation unchanged.
# The %(name)s form (Python named percent formatting, used by gettext/Jinja plurals)
# must come before %[sdif] so the named variant is matched as a whole.
PLACEHOLDER_RE: Final = re.compile(r"(\{[^}]+\}|%\([^)]+\)[sdif]|%[sdif]|%\d+\$s)")
TRAILING_WHITESPACE_RE: Final = re.compile(r"(\s+)$")
NPLURALS_RE: Final = re.compile(r"nplurals\s*=\s*(\d+)")


# Default base URLs per model prefix — prevents env-var bleed across providers.
# (e.g. OPENAI_BASE_URL pointing to Ollama would otherwise break openai/* models)
_PREFIX_BASE_URLS: Final[dict[str, str]] = {
    "ollama": "http://localhost:11434",
    "openai": "https://api.openai.com/v1",
}

# Providers used in the Makefile that require an API key env var.
# ollama runs locally and needs no key.
_PROVIDER_API_KEY_ENV: Final[dict[str, str]] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class LiteLLMProvider:
    """Provider-agnostic LLM client backed by litellm."""

    def __init__(self, model: str, base_url: str | None = None) -> None:
        self._model = model
        prefix = model.split("/", maxsplit=1)[0] if "/" in model else ""
        self._base_url = base_url or _PREFIX_BASE_URLS.get(prefix)
        required_env = _PROVIDER_API_KEY_ENV.get(prefix)
        if required_env and not os.environ.get(required_env):
            msg = (
                f"Provider {prefix!r} requires {required_env} to be set. "
                f"Add it to the .env file at the repo root, e.g.:\n  {required_env}=your-key-here"
            )
            raise typer.BadParameter(msg, param_hint="--model")

    def _generate_json(self, prompt: str) -> dict[str, str]:
        kwargs: dict = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": 1000,
            "messages": [
                {"role": "system", "content": "Return valid JSON only, no markdown."},
                {"role": "user", "content": prompt},
            ],
        }
        if self._base_url:
            kwargs["api_base"] = self._base_url
        response = litellm.completion(**kwargs)
        raw = (response.choices[0].message.content or "").strip()
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.MULTILINE).strip()
        return json.loads(raw)


class DryRunProvider:
    """Provider stand-in for `--dry-run`: composes/logs the prompt but never calls the LLM.

    Same `_generate_json` interface as `LiteLLMProvider` (duck-typed), so the whole
    translation pipeline runs unchanged. It needs no API key and no model validation;
    it prints the composed prompt to the console and returns a fixed stub so the run
    can be inspected without spending tokens.
    """

    _STUB: Final[dict[str, str]] = {"interpretation": "(dry-run)", "translation": "(dry-run)"}

    def _generate_json(self, prompt: str) -> dict[str, str]:
        console.print("[dim]\\[dry-run prompt][/dim]")
        console.print(prompt)
        return dict(self._STUB)


# ---------------------------------------------------------------------------
# Model discovery / validation
# ---------------------------------------------------------------------------


def _models_by_provider() -> dict[str, list[str]]:
    """litellm's known models grouped by provider, sorted for stable display."""
    grouped = litellm.models_by_provider
    return {provider: sorted(grouped[provider]) for provider in sorted(grouped)}


def _validate_model(model: str) -> None:
    """Raise typer.BadParameter if litellm does not recognise the model."""
    if model in litellm.model_list:
        return
    # Custom/self-hosted models use a known provider prefix (e.g. openai/my-model).
    prefix = model.split("/", maxsplit=1)[0] if "/" in model else ""
    if prefix in litellm.models_by_provider:
        return
    msg = f"Unknown model {model!r}. Run `models` to list known models/providers."
    raise typer.BadParameter(msg)


# ---------------------------------------------------------------------------
# Placeholder protection
# ---------------------------------------------------------------------------


def _protect(text: str) -> ProtectedText:
    """Replace placeholders with tokens ⟨0⟩, ⟨1⟩ ... before sending to AI."""
    mapping: PlaceholderMapDict = {}

    def replace(m: re.Match[str]) -> PlaceholderTokenStr:
        token = f"⟨{len(mapping)}⟩"
        mapping[token] = m.group(0)
        return token

    return ProtectedText(PLACEHOLDER_RE.sub(replace, text), mapping)


def _restore(text: str, mapping: PlaceholderMapDict) -> str:
    for token, original in mapping.items():
        text = text.replace(token, original)
    return text


def _normalize_trailing_whitespace(msgid: str, translated: str) -> str:
    """Match msgid trailing-whitespace intent while removing accidental LLM tails."""
    src_match = TRAILING_WHITESPACE_RE.search(msgid)
    src_suffix = src_match.group(1) if src_match else ""
    return translated.rstrip() + src_suffix


def _extract_translator_notes(comment: str) -> str:
    """Extract @TRANSLATOR guidance lines from xgettext extracted comments."""
    notes: list[str] = []
    for raw_line in comment.splitlines():
        line = raw_line.strip()
        if line.startswith(TRANSLATOR_TAG):
            notes.append(line[len(TRANSLATOR_TAG) :].strip())
        elif line:
            notes.append(line)
    return "\n".join(notes)


def _get_nplurals(po: polib.POFile) -> int:
    """Return the number of plural forms declared in the catalog's Plural-Forms header.

    Falls back to 2 (the gettext default) when the header is missing or unparsable.
    """
    match = NPLURALS_RE.search(po.metadata.get("Plural-Forms", ""))
    return max(1, int(match.group(1))) if match else 2


def _is_untranslated(entry: polib.POEntry) -> bool:
    """True when an entry has no complete translation (plural-aware).

    Plural entries store translations in ``msgstr_plural`` (msgstr stays empty), so a
    plain ``not entry.msgstr`` check would mark every plural entry as untranslated.
    """
    if entry.msgid_plural:
        plural = entry.msgstr_plural or {}
        return not plural or any(not (text or "").strip() for text in plural.values())
    return not entry.msgstr or entry.msgstr.strip() == ""


def _save_po_atomic(po: polib.POFile, out: Path) -> None:
    """Write a PO file via a temp file and atomic replace."""
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_out = out.with_name(f"{out.name}.tmp")
    with _PO_SAVE_LOCK:
        po.save(str(temp_out))
        temp_out.replace(out)


# ---------------------------------------------------------------------------
# AI translation call
# ---------------------------------------------------------------------------


def _filter_glossary(glossary: TermGlossaryDict, msgid: str, snippet: str) -> TermGlossaryDict:
    """Keep only glossary terms that appear (case-insensitively) in the msgid or snippet.

    Passing the full glossary on every entry adds terms irrelevant to that particular
    string; filtering keeps the prompt minimal and reduces noise.
    """
    haystack = f"{msgid} {snippet}".lower()
    return {term: translation for term, translation in glossary.items() if term.lower() in haystack}


def _translate_entry(  # noqa: C901
    provider: LiteLLMProvider | DryRunProvider,
    msgid: str,
    snippet: str,
    translator_notes: str,
    lang_name: LangNameStr,
    glossary: TermGlossaryDict,
    occurrences: list[tuple[str, str]] | None = None,
    msgid_plural: str = "",
    logger: logging.Logger | None = None,
) -> Translation:
    """Translate one msgid; the context interpretation is always regenerated fresh.

    When ``msgid_plural`` is set the entry is pluralized: both the singular and the
    plural English source forms are translated and returned (``Translation.text`` and
    ``Translation.text_plural``).
    """
    protected = _protect(msgid)
    is_plural = bool(msgid_plural)
    protected_plural = _protect(msgid_plural) if is_plural else None

    interp_instruction = (
        "Write a one-sentence context interpretation explaining where/how this string "
        "appears (max ~150 characters, a single sentence, no line breaks)."
    )

    # Assemble the prompt from sections; skip blocks that have nothing to say so
    # the model isn't given dead instructions (no snippet / no placeholders).
    sections = [
        "You are a technical software localizer for a scientific simulation application.",
        f"Target language: {lang_name}",
    ]

    if glossary:
        glossary_block = "\n".join(f"  {source_term} → {target_term}" for source_term, target_term in glossary.items())
        sections.append(f"Glossary (use these translations for these terms):\n{glossary_block}")

    if translator_notes.strip(": "):
        sections.append(f"Translator notes from maintainers (follow these instructions):\n{translator_notes}")

    if snippet.strip():
        sections.append(
            "Source code snippet around this translatable string (line marked >>> is the "
            "string itself). This is a snapshot of the surrounding code, not the full file "
            "-- use it, and the file path(s) below, to infer the context and meaning of the "
            f"string:\n{snippet}"
        )

    if occurrences:
        max_shown = 5
        shown = occurrences[:max_shown]
        loc_lines = "\n".join(f"  - {filepath}:{lineno}" for filepath, lineno in shown)
        if len(occurrences) > max_shown:
            loc_lines += f"\n  ... and {len(occurrences) - max_shown} more location(s)"
        sections.append(f"File path(s) where this string is used (may hint at its domain/purpose):\n{loc_lines}")

    if is_plural:
        assert protected_plural is not None  # nosec
        sections.append(
            "This is a pluralized string. Translate BOTH grammatical forms:\n"
            f'  singular (used when count == 1): "{protected.text}"\n'
            f'  plural   (used when count != 1): "{protected_plural.text}"'
        )
    else:
        sections.append(f'String to translate:\n"{protected.text}"')

    if protected.mapping or (protected_plural and protected_plural.mapping):
        sections.append("Placeholders like ⟨0⟩ ⟨1⟩ must appear unchanged in the translation.")

    sections.append(interp_instruction)

    if is_plural:
        sections.append(
            "Respond with JSON only, no markdown:\n"
            "{\n"
            '  "interpretation": "<one sentence>",\n'
            '  "translation": "<translated singular string>",\n'
            '  "translation_plural": "<translated plural string>"\n'
            "}"
        )
    else:
        sections.append(
            "Respond with JSON only, no markdown:\n"
            "{\n"
            '  "interpretation": "<one sentence>",\n'
            '  "translation": "<translated string>"\n'
            "}"
        )

    prompt = "\n\n".join(sections)

    if logger:
        logger.debug("--- PROMPT [%s] %r ---\n%s", lang_name, msgid, prompt)

    data = provider._generate_json(prompt)  # noqa: SLF001

    if logger:
        logger.debug("--- RESPONSE ---\n%s", json.dumps(data, ensure_ascii=False, indent=2))

    translated = _restore(data["translation"], protected.mapping)
    text = _normalize_trailing_whitespace(msgid, translated)

    text_plural: str | None = None
    if is_plural:
        assert protected_plural is not None  # nosec
        raw_plural = data.get("translation_plural") or data["translation"]
        restored_plural = _restore(raw_plural, protected_plural.mapping)
        text_plural = _normalize_trailing_whitespace(msgid_plural, restored_plural)

    return Translation(data["interpretation"], text, text_plural)


def _build_translation_job(
    entry: polib.POEntry,
    provider: LiteLLMProvider | DryRunProvider,
    lang_name: LangNameStr,
    glossary: TermGlossaryDict,
    snippet_by_msgid: dict[str, str],
    logger: logging.Logger | None = None,
    *,
    force: bool = False,
) -> TranslationJob:
    """Compute a translation job without mutating shared PO state.

    Change detection is intentionally minimal: an entry is (re)translated only when
    it is untranslated or flagged ``fuzzy`` (both set by ``msgmerge`` precisely when
    the ``msgid`` changes). ``force`` bypasses this to (re)translate every matched
    entry. Source snippets come from ``snippet_by_msgid`` (built from the .pot), never
    from the .po -- the shipped .po stays snippet-free.
    """
    if force:
        # Bypass change detection: --force / --filter always (re)translate matched entries.
        state: EntryState = EntryNew(entry=entry) if _is_untranslated(entry) else EntryUpdated(entry=entry)
    else:
        state = _classify_entry_state(entry)
    if isinstance(state, EntrySkipped):
        return TranslationSkipped(entry=entry)

    snippet = snippet_by_msgid.get(entry.msgid, "")
    try:
        result = _translate_entry(
            provider=provider,
            msgid=entry.msgid,
            snippet=snippet,
            translator_notes=_extract_translator_notes(entry.comment or ""),
            lang_name=lang_name,
            glossary=_filter_glossary(glossary, entry.msgid, snippet),
            occurrences=entry.occurrences,
            msgid_plural=entry.msgid_plural or "",
            logger=logger,
        )
    except Exception as e:
        return TranslationFailed(entry=entry, error=str(e))

    return TranslationCompleted(entry=entry, state=state, result=result)


# ---------------------------------------------------------------------------
# Comment parsing helpers
# ---------------------------------------------------------------------------


def _snippet_from_comment(comment: str) -> str:
    """Return the CTX-SNIPPET block (source-code context) from a # comment block.

    Snippets live only in the .pot; this reads them back so the LLM prompt has
    source context. The shipped .po itself is kept snippet-free (see _clean_tcomment).
    """
    snippet_lines: list[str] = []
    in_snippet = False
    for raw in comment.splitlines():
        line = raw.strip()
        if line.startswith("CTX-SNIPPET:"):
            in_snippet = True
            continue
        if line.startswith("CTX-"):
            in_snippet = False
            continue
        if in_snippet:
            snippet_lines.append(line)
    return "\n".join(snippet_lines)


def _clean_tcomment(comment: str, interp: str | None) -> str:
    """Strip CTX-SNIPPET / CTX-SNIPPET-VERSION / CTX-VERSION from a # comment block.

    Non-CTX passthrough lines are preserved. CTX-INTERPRETATION is the only CTX field
    kept in the .po: when *interp* is given it is (re)written; when None an existing
    CTX-INTERPRETATION is preserved. This keeps the shipped .po lean (no multi-line
    code snippets, no git/timestamp version stamps).
    """
    passthrough: list[str] = []
    existing_interp: str | None = None
    in_snippet = False
    for raw in comment.splitlines():
        line = raw.strip()
        if line.startswith("CTX-SNIPPET:"):
            in_snippet = True
            continue
        if line.startswith("CTX-INTERPRETATION:"):
            in_snippet = False
            existing_interp = line[len("CTX-INTERPRETATION:") :].strip()
            continue
        if line.startswith("CTX-"):  # CTX-SNIPPET-VERSION, CTX-VERSION, ...
            in_snippet = False
            continue
        if in_snippet:
            continue
        passthrough.append(raw)

    lines = [line for line in passthrough if line.strip()]
    final_interp = interp if interp is not None else existing_interp
    if final_interp:
        lines.append(f"CTX-INTERPRETATION: {final_interp}")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def _needs_translation(entry: polib.POEntry) -> bool:
    """True when an entry must be (re)translated.

    Only two native gettext signals trigger work, both set by ``msgmerge`` exactly
    when the source ``msgid`` changes:
      - untranslated (new/changed msgid with no close match)
      - ``fuzzy`` flag (changed msgid fuzzy-matched to a prior translation)
    Line references, comments, and header timestamps are deliberately ignored.
    """
    return _is_untranslated(entry) or "fuzzy" in entry.flags


def _classify_entry_state(entry: polib.POEntry) -> EntryState:
    """Return explicit new/updated/skipped entry state objects for translation routing."""
    if _is_untranslated(entry):
        return EntryNew(entry=entry)
    if "fuzzy" in entry.flags:
        return EntryUpdated(entry=entry)
    return EntrySkipped(entry=entry)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

app = typer.Typer(
    add_completion=False,
    help="AI-translate a .pot file with litellm.",
    no_args_is_help=True,
)


def _build_logger(log_file: Path | None) -> logging.Logger | None:
    if not log_file:
        return None
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.touch(exist_ok=True)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s\n%(message)s\n", datefmt="%Y-%m-%dT%H:%M:%SZ"))
    logger = logging.getLogger("i18n_translator")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    console.print(f"[dim]\\[log] writing prompts/responses to {log_file}[/dim]")
    return logger


@app.command()
def translate(  # noqa: C901, PLR0912, PLR0913, PLR0915
    out: Path = typer.Option(..., help="Output .po file path"),
    pot: Path = typer.Option(Path("messages.pot"), help="Source .pot template"),
    in_po: Path | None = typer.Option(
        None,
        help="Optional existing merged .po input (typically after msgmerge)",
    ),
    lang: str = typer.Option("zh_CN", help="Target language code, e.g. zh_CN"),
    model: str = typer.Option(
        "ollama/llama3.1",
        envvar="AI_TRANSLATE_MODEL",
        help="litellm model string, e.g. ollama/llama3.1, openai/gpt-4o",
    ),
    base_url: str | None = typer.Option(
        None,
        envvar="AI_TRANSLATE_BASE_URL",
        help="Override API base URL (self-hosted OpenAI-compatible endpoints)",
    ),
    glossary_file: Path = typer.Option(Path(DEFAULT_GLOSSARY_FILE), "--glossary", help="Path to glossary JSON file"),
    log_file: Path | None = typer.Option(
        None,
        help=("Append AI prompts and responses to this file for review (default: <out_dir>/translate.log)"),
    ),
    incremental_save: bool = typer.Option(
        True,
        "--incremental-save/--no-incremental-save",
        help="Persist the output file after each translated entry.",
    ),
    progress: bool = typer.Option(
        True,
        "--progress/--no-progress",
        help="Show live translation progress.",
    ),
    parallel: bool = typer.Option(
        True,
        "--parallel/--no-parallel",
        help="Translate entries concurrently using a thread pool (default: parallel).",
    ),
    max_workers: int = typer.Option(
        4,
        min=1,
        help="Maximum number of concurrent translation workers when parallel mode is enabled.",
    ),
    msgid_filter: str | None = typer.Option(
        None,
        "--filter",
        help=(
            "Only translate entries whose msgid matches this glob pattern (fnmatch). "
            "Implies --force for matched entries."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Force (re)translation even if entries appear fresh, bypassing the change-detection check.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Compose and log the exact LLM prompts (with a stub '(dry-run)' response) for "
            "entries that WOULD be translated, without calling the LLM or saving. Spends no "
            "tokens and needs no API key; prompts are printed and appended to the log file."
        ),
    ),
) -> None:
    """Translate a .pot/.po catalog into a language-specific .po."""
    if dry_run:
        parallel = False
        progress = False
        incremental_save = False
    else:
        _validate_model(model)

    data = _load_glossary(str(glossary_file))
    glossary = data.glossaries.get(lang, {})
    lang_name = data.lang_names.get(lang, lang)

    effective_log_file = log_file or (out.parent / "translate.log")
    logger = _build_logger(effective_log_file)
    provider: LiteLLMProvider | DryRunProvider = (
        DryRunProvider() if dry_run else LiteLLMProvider(model=model, base_url=base_url)
    )
    if dry_run:
        console.print("[bold]\\[provider][/bold] dry-run (no LLM call, nothing saved)")
    else:
        console.print(f"[bold]\\[provider][/bold] model={model}" + (f" base_url={base_url}" if base_url else ""))

    # Ollama serves from a single local model instance, so client-side threads do not
    # translate into real concurrency unless the server is explicitly configured for it.
    # Warn instead of leaving the impression that --parallel sped things up.
    if not dry_run and parallel and max_workers > 1 and model.split("/", maxsplit=1)[0] == "ollama":
        console.print(
            "[yellow]\\[warning][/yellow] Ollama runs one local model instance: --parallel "
            f"(--max-workers {max_workers}) will NOT speed up translation unless the Ollama server "
            "is configured for concurrency (set OLLAMA_NUM_PARALLEL and ensure enough VRAM). "
            "Requests will effectively run one at a time."
        )

    source_path = in_po if in_po and in_po.exists() else pot
    po = polib.pofile(str(source_path))
    # Ensure save() writes UTF-8 even when template headers still advertise CHARSET.
    po.encoding = "utf-8"
    po.metadata["Language"] = lang
    po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    po.metadata["Content-Transfer-Encoding"] = "8bit"
    nplurals = _get_nplurals(po)

    # Source snippets live only in the .pot; build a msgid -> snippet map for prompt
    # context, then strip any snippet/version stamps carried into the working .po so
    # the shipped catalog stays lean (only msgstr + CTX-INTERPRETATION).
    pot_catalog = polib.pofile(str(pot))
    snippet_by_msgid = {entry.msgid: _snippet_from_comment(entry.tcomment or "") for entry in pot_catalog}
    for entry in po:
        entry.tcomment = _clean_tcomment(entry.tcomment or "", None)

    total = translated = skipped = new_count = updated_count = errors = 0

    def apply_job(job: TranslationJob) -> None:
        nonlocal translated, skipped, new_count, updated_count, errors

        if isinstance(job, TranslationSkipped):
            console.print(f"  [dim]\\[skip][/dim] {job.entry.msgid!r}")
            skipped += 1
            return

        if isinstance(job, TranslationFailed):
            errors += 1
            console.print(f"    [red]\\[ERROR][/red] {job.error}")
            return

        assert isinstance(job, TranslationCompleted)
        console.print(f"  [cyan]\\[translate][/cyan] {job.entry.msgid!r}")

        state = job.state

        with _PO_SAVE_LOCK:
            if job.entry.msgid_plural:
                # Plural entries serialize from msgstr_plural; polib ignores msgstr.
                # Map the two translated English forms onto the target locale's plural
                # indices: index 0 is the singular form when the locale has >1 form,
                # every other index uses the plural form (1-form locales use plural).
                singular = job.result.text
                plural = job.result.text_plural or job.result.text
                job.entry.msgstr_plural = {
                    i: (singular if nplurals > 1 and i == 0 else plural) for i in range(nplurals)
                }
            else:
                job.entry.msgstr = job.result.text
            job.entry.tcomment = _clean_tcomment(job.entry.tcomment or "", job.result.interpretation)
            job.entry.flags = [f for f in job.entry.flags if f != "fuzzy"]

            console.print(f"    [green]→[/green] {job.result.text!r}")
            console.print(f"    [dim]CTX-INTERPRETATION: {job.result.interpretation}[/dim]")

        translated += 1
        if isinstance(state, EntryNew):
            new_count += 1
        elif isinstance(state, EntryUpdated):
            updated_count += 1
        else:
            msg = f"Unexpected translation state: {type(state)!r}"
            raise TypeError(msg)

        if incremental_save and not dry_run:
            _save_po_atomic(po, out)

    entries = list(po)
    if msgid_filter:
        entries = [e for e in entries if fnmatch(e.msgid, msgid_filter)]
        entry_word = "entry" if len(entries) == 1 else "entries"
        console.print(f"[bold]\\[filter][/bold] {len(entries)} {entry_word} match {msgid_filter!r}")
    effective_force = force or bool(msgid_filter)

    # Pre-flight plan: classify the (filtered) entries once so the user sees the scope
    # -- how many are NEW (untranslated), UPDATE (fuzzy/changed msgid), or SKIP (fresh) --
    # and thus the up-front estimate of how many will actually be sent to the model.
    if effective_force:
        plan_new = sum(1 for e in entries if _is_untranslated(e))
        plan_update = len(entries) - plan_new
        plan_skip = 0
    else:
        plan_states = [_classify_entry_state(e) for e in entries]
        plan_new = sum(1 for s in plan_states if isinstance(s, EntryNew))
        plan_update = sum(1 for s in plan_states if isinstance(s, EntryUpdated))
        plan_skip = sum(1 for s in plan_states if isinstance(s, EntrySkipped))
    plan_to_model = plan_new + plan_update
    console.print(
        f"[bold]\\[plan][/bold] {lang}: {len(po)} messages (template {len(pot_catalog)}) \u00b7 "
        f"[cyan]{plan_new} NEW[/cyan] \u00b7 [yellow]{plan_update} UPDATE[/yellow] \u00b7 "
        f"[dim]{plan_skip} SKIP[/dim] \u2192 {plan_to_model} to model"
    )

    if progress:
        progress_bar = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeRemainingColumn(),
            console=console,
            transient=False,
        )
        with progress_bar:
            task = progress_bar.add_task("Translating", total=len(entries))
            if parallel:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(
                            _build_translation_job,
                            entry,
                            provider,
                            lang_name,
                            glossary,
                            snippet_by_msgid,
                            logger,
                            force=effective_force,
                        )
                        for entry in entries
                    ]
                    for future in as_completed(futures):
                        apply_job(future.result())
                        total += 1
                        progress_bar.update(
                            task,
                            advance=1,
                            description=f"Translating {translated} done / {skipped} skipped / {errors} errors",
                        )
            else:
                for entry in entries:
                    job = _build_translation_job(
                        entry,
                        provider,
                        lang_name,
                        glossary,
                        snippet_by_msgid,
                        logger,
                        force=effective_force,
                    )
                    apply_job(job)
                    total += 1
                    progress_bar.update(
                        task,
                        advance=1,
                        description=f"Translating {translated} done / {skipped} skipped / {errors} errors",
                    )
    elif parallel:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _build_translation_job,
                    entry,
                    provider,
                    lang_name,
                    glossary,
                    snippet_by_msgid,
                    logger,
                    force=effective_force,
                )
                for entry in entries
            ]
            for future in as_completed(futures):
                apply_job(future.result())
                total += 1
    else:
        for entry in entries:
            job = _build_translation_job(
                entry,
                provider,
                lang_name,
                glossary,
                snippet_by_msgid,
                logger,
                force=effective_force,
            )
            apply_job(job)
            total += 1

    summary_label = "dry-run" if dry_run else "done"
    translated_label = "would translate" if dry_run else "translated"
    console.print(
        f"\n[bold]\\[{summary_label}][/bold] {total} entries: "
        f"[green]{translated} {translated_label}[/green], "
        f"[cyan]{new_count} NEW[/cyan], "
        f"[yellow]{updated_count} UPDATED[/yellow], "
        f"[dim]{skipped} SKIPPED[/dim], "
        f"[red]{errors} ERRORS[/red]"
    )

    if not dry_run:
        if not incremental_save:
            _save_po_atomic(po, out)
        console.print(f"[bold]\\[saved][/bold] {out}")


@app.command()
def models(
    provider: str | None = typer.Option(None, help="Only show models for this provider prefix, e.g. openai"),
) -> None:
    """List the models litellm knows about, grouped by provider."""
    grouped = _models_by_provider()
    if provider:
        if provider not in grouped:
            msg = f"Unknown provider {provider!r}."
            raise typer.BadParameter(msg)
        grouped = {provider: grouped[provider]}

    table = Table(title="litellm models by provider")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Models", style="green")
    for name, model_names in grouped.items():
        table.add_row(name, ", ".join(model_names))
    console.print(table)


if __name__ == "__main__":
    app()
