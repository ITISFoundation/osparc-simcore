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
    - Reads CTX-SNIPPET / CTX-INTERPRETATION from translator comments for context
    - Includes extracted @TRANSLATOR notes, glossary terms, and source snippet in the prompt
    - LLM returns: context interpretation + translation
        - Writes back CTX-INTERPRETATION, CTX-VERSION, and msgstr
    - Supports sequential or threaded translation, live progress, and incremental atomic saves
    - Uses git-blame freshness checks with timestamp fallback when git is unavailable

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
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, NamedTuple

import litellm
import polib
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

DEFAULT_GLOSSARY_FILE = "glossary.json"

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


class TranslatorContext(NamedTuple):
    snippet: str
    snippet_version: str
    interp: str
    version: str


@dataclass(frozen=True)
class BlameCommitFound:
    commit: str  # explicit success branch for git blame lookups


@dataclass(frozen=True)
class BlameCommitUnknown:
    pass  # explicit failure branch when git blame is unavailable


type BlameCommitResult = BlameCommitFound | BlameCommitUnknown


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
    version: str


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


# Placeholders like {min_size} or %s must survive translation unchanged
PLACEHOLDER_RE: Final = re.compile(r"(\{[^}]+\}|%[sdif]|%\d+\$s)")
TRAILING_WHITESPACE_RE: Final = re.compile(r"(\s+)$")


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
        if line.startswith("@TRANSLATOR"):
            notes.append(line[len("@TRANSLATOR") :].strip())
        elif line:
            notes.append(line)
    return "\n".join(notes)


def _parse_catalog_timestamp(value: str) -> datetime | None:
    """Parse gettext timestamps like '2026-06-24 10:15+0000' or ISO UTC."""
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M%z", "%Y-%m-%d %H:%M:%S%z"):
        try:
            return datetime.strptime(text, fmt)  # noqa: DTZ007  # fmt includes %z
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_ctx_version(version: str) -> tuple[str, datetime | None]:
    """Parse CTX-VERSION as '<commit> <timestamp>' and return parts."""
    parts = version.split(maxsplit=1)
    commit = parts[0] if parts else ""
    timestamp = _parse_catalog_timestamp(parts[1]) if len(parts) > 1 else None
    return commit, timestamp


def _save_po_atomic(po: polib.POFile, out: Path) -> None:
    """Write a PO file via a temp file and atomic replace."""
    out.parent.mkdir(parents=True, exist_ok=True)
    temp_out = out.with_name(f"{out.name}.tmp")
    with _PO_SAVE_LOCK:
        po.save(str(temp_out))
        temp_out.replace(out)


# ---------------------------------------------------------------------------
# Git commit hash for the source file at a given line
# ---------------------------------------------------------------------------


def _git_repo_root() -> str | None:
    """Return the absolute repo root, or None if not in a git repo."""
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],  # noqa: S607
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            or None
        )
    except Exception:
        return None


_REPO_ROOT: Final[str | None] = _git_repo_root()


def _get_blame_commit(filepath: str, lineno: int) -> BlameCommitResult:
    """Returns short commit hash for the given file:line, or 'unknown'.

    Handles uncommitted changes by attempting to get the previous commit.
    filepath is relative to the repo root.
    """
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "blame", "-L", f"{lineno},{lineno}", "--porcelain", filepath],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=_REPO_ROOT,
        )
        first_line = result.stdout.splitlines()[0]
        commit = first_line.split()[0][:7]

        # If git blame returns 00000000 (uncommitted), try to get HEAD commit instead
        if commit == "0000000":
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],  # noqa: S607
                    capture_output=True,
                    text=True,
                    check=True,
                )
                commit = result.stdout.strip()[:7]
            except Exception:
                commit = "unknown"

        return BlameCommitFound(commit=commit)
    except Exception:
        return BlameCommitUnknown()


# ---------------------------------------------------------------------------
# AI translation call
# ---------------------------------------------------------------------------


def _translate_entry(
    provider: LiteLLMProvider,
    msgid: str,
    snippet: str,
    translator_notes: str,
    existing_interp: str,
    lang_name: LangNameStr,
    glossary: TermGlossaryDict,
    logger: logging.Logger | None = None,
) -> Translation:
    """Translate one msgid; reuses existing_interp when already computed (cached)."""
    protected = _protect(msgid)

    # If we already have a CTX-INTERPRETATION, skip re-interpreting (saves tokens)
    interp_instruction = (
        f"Reuse the existing context interpretation below (do not regenerate it):\n{existing_interp}"
        if existing_interp and existing_interp != "(pending)"
        else "Write a one-sentence context interpretation explaining where/how this string appears."
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

    if translator_notes.strip():
        sections.append(f"Translator notes from maintainers (follow these instructions):\n{translator_notes}")

    if snippet.strip():
        sections.append(f"Source code context (the string appears at the line marked >>>):\n{snippet}")

    sections.append(f'String to translate:\n"{protected.text}"')

    if protected.mapping:
        sections.append("Placeholders like ⟨0⟩ ⟨1⟩ must appear unchanged in the translation.")

    sections.append(interp_instruction)

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
    return Translation(data["interpretation"], _normalize_trailing_whitespace(msgid, translated))


def _build_translation_job(
    entry: polib.POEntry,
    provider: LiteLLMProvider,
    lang_name: LangNameStr,
    glossary: TermGlossaryDict,
    use_git: bool,
    pot_creation_at: datetime | None,
    logger: logging.Logger | None = None,
) -> TranslationJob:
    """Compute a translation job without mutating shared PO state."""
    ctx = _parse_translator_comments(entry)
    state = _classify_entry_state(
        entry=entry,
        ctx=ctx,
        use_git=use_git,
        pot_creation_at=pot_creation_at,
    )
    if isinstance(state, EntrySkipped):
        return TranslationSkipped(entry=entry)

    try:
        result = _translate_entry(
            provider=provider,
            msgid=entry.msgid,
            snippet=ctx.snippet,
            translator_notes=_extract_translator_notes(entry.comment or ""),
            existing_interp=ctx.interp,
            lang_name=lang_name,
            glossary=glossary,
            logger=logger,
        )
    except Exception as e:
        return TranslationFailed(entry=entry, error=str(e))

    version = "unknown"
    if entry.occurrences:
        filepath, lineno_str = entry.occurrences[0]
        if lineno_str:
            commit_result = _get_blame_commit(filepath, int(lineno_str))
            commit = commit_result.commit if isinstance(commit_result, BlameCommitFound) else "unknown"
            ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            version = f"{commit} {ts}"

    return TranslationCompleted(entry=entry, state=state, result=result, version=version)


# ---------------------------------------------------------------------------
# Comment parsing helpers
# ---------------------------------------------------------------------------


def _parse_translator_comments(entry: polib.POEntry) -> TranslatorContext:
    """Extract Pass-2 enrichment fields (CTX-SNIPPET, CTX-INTERPRETATION, CTX-VERSION) from # comment lines."""
    snippet_lines: list[str] = []
    interp = version = snippet_version = ""
    in_snippet = False
    # CTX-* fields are stored in translator comments (# => tcomment).
    # Fallback to extracted comments for backward compatibility.
    comment_block = entry.tcomment or entry.comment or ""
    for line in comment_block.splitlines():
        line = line.strip()  # noqa: PLW2901
        if line.startswith("CTX-SNIPPET:"):
            in_snippet = True
        elif line.startswith("CTX-INTERPRETATION:"):
            in_snippet = False
            interp = line[len("CTX-INTERPRETATION:") :].strip()
        elif line.startswith("CTX-SNIPPET-VERSION:"):
            in_snippet = False
            snippet_version = line[len("CTX-SNIPPET-VERSION:") :].strip()
        elif line.startswith("CTX-VERSION:"):
            in_snippet = False
            version = line[len("CTX-VERSION:") :].strip()
        elif in_snippet:
            snippet_lines.append(line)
    return TranslatorContext("\n".join(snippet_lines), snippet_version, interp, version)


def _update_comment(comment: str, interp: str, version: str) -> str:
    """Rewrite Pass-2 enrichment fields CTX-INTERPRETATION and CTX-VERSION in the # comment block."""
    new_lines = []
    saw_interp = False
    for line in comment.splitlines():
        stripped = line.strip()
        # Skip old CTX-VERSION lines - they will be re-added below
        if stripped.startswith("CTX-VERSION:"):
            continue
        if stripped.startswith("CTX-INTERPRETATION:"):
            new_lines.append(f"CTX-INTERPRETATION: {interp}")
            saw_interp = True
        else:
            new_lines.append(line)

    if not saw_interp:
        new_lines.append(f"CTX-INTERPRETATION: {interp}")

    # Always add the fresh CTX-VERSION at the end
    new_lines.append(f"CTX-VERSION: {version}")

    return "\n".join(new_lines)


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------


def _is_stale(  # noqa: PLR0911
    entry: polib.POEntry,
    ctx: TranslatorContext,
    use_git: bool,
    pot_creation_at: datetime | None,
) -> bool:
    """
    An entry needs (re)translation if:
      - msgstr is empty
      - flagged fuzzy
    - CTX-VERSION is pending/unknown (not yet translated)
      - git blame commit differs from stored commit (code changed around string)
    """
    if not entry.msgstr or entry.msgstr.strip() == "":
        return True
    if "fuzzy" in entry.flags:
        return True
    if ctx.version in ("(pending)", "unknown", ""):
        return True

    stored_commit, translated_at = _parse_ctx_version(ctx.version)
    if stored_commit in ("", "unknown"):
        return True

    # Check git blame for first occurrence
    if use_git and entry.occurrences:
        filepath, lineno_str = entry.occurrences[0]
        try:
            current = _get_blame_commit(filepath, int(lineno_str)) if lineno_str else None
            if isinstance(current, BlameCommitFound):
                return current.commit != stored_commit
        except Exception:  # noqa: S110
            pass

    # Fallback for no-git mode or git lookup failures.
    if pot_creation_at and translated_at:
        return pot_creation_at > translated_at

    # Conservative fallback: if freshness can't be proven, mark stale.
    return True


def _classify_entry_state(
    entry: polib.POEntry,
    ctx: TranslatorContext,
    use_git: bool,
    pot_creation_at: datetime | None,
) -> EntryState:
    """Return explicit new/updated/skipped entry state objects for translation routing."""
    if not entry.msgstr or entry.msgstr.strip() == "":
        return EntryNew(entry=entry)
    if "fuzzy" in entry.flags:
        return EntryUpdated(entry=entry)
    return EntryUpdated(entry=entry) if _is_stale(entry, ctx, use_git, pot_creation_at) else EntrySkipped(entry=entry)


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
def translate(  # noqa: C901, PLR0913, PLR0915
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
    use_git: bool = typer.Option(
        True,
        "--use-git/--no-git",
        help="Use git blame commit checks for staleness; fallback to timestamps when unavailable.",
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
        False,
        "--parallel/--no-parallel",
        help="Translate entries concurrently using a thread pool.",
    ),
    max_workers: int = typer.Option(
        4,
        min=1,
        help="Maximum number of concurrent translation workers when parallel mode is enabled.",
    ),
    dry_run: bool = typer.Option(False, help="Print without saving"),
) -> None:
    """Translate a .pot/.po catalog into a language-specific .po."""
    _validate_model(model)

    data = _load_glossary(str(glossary_file))
    glossary = data.glossaries.get(lang, {})
    lang_name = data.lang_names.get(lang, lang)

    effective_log_file = log_file or (out.parent / "translate.log")
    logger = _build_logger(effective_log_file)
    provider = LiteLLMProvider(model=model, base_url=base_url)
    console.print(f"[bold]\\[provider][/bold] model={model}" + (f" base_url={base_url}" if base_url else ""))

    source_path = in_po if in_po and in_po.exists() else pot
    po = polib.pofile(str(source_path))
    # Ensure save() writes UTF-8 even when template headers still advertise CHARSET.
    po.encoding = "utf-8"
    po.metadata["Language"] = lang
    po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    po.metadata["Content-Transfer-Encoding"] = "8bit"
    pot_creation_at = _parse_catalog_timestamp(po.metadata.get("POT-Creation-Date", ""))

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
            job.entry.msgstr = job.result.text
            job.entry.tcomment = _update_comment(
                job.entry.tcomment or job.entry.comment or "",
                job.result.interpretation,
                job.version,
            )
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
                            use_git,
                            pot_creation_at,
                            logger,
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
                        use_git,
                        pot_creation_at,
                        logger,
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
                    use_git,
                    pot_creation_at,
                    logger,
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
                use_git,
                pot_creation_at,
                logger,
            )
            apply_job(job)
            total += 1

    console.print(
        f"\n[bold]\\[done][/bold] {total} entries: "
        f"[green]{translated} translated[/green], "
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
