# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "Babel>=2.12.0",
#   "Jinja2>=3.0.0",
#   "polib>=1.2.0",
#   "rich>=13.0.0",
#   "typer>=0.12.0",
# ]
# ///
# ruff: noqa: B008
"""
tools/i18n_extractor.py
Two-step .pot extractor:

    Step 1 — xgettext: run xgettext over source files.
                     Handles Python, C++, and MFC .rc files. Produces a
                     standard .pot with #: filepath:lineno references.

    Step 1b — jinja: run Babel over Jinja2 templates ({% trans %} blocks and
                     {{ gettext(...) }} calls). xgettext cannot parse Jinja2,
                     so Babel's jinja2.ext.babel_extract is used. Produces a
                     .pot with the same #: filepath:lineno references.

    Step 2 — enrich: for each entry, read #: references to load
                     surrounding source lines (CTX-SNIPPET) and write a
             extractor-owned snippet freshness marker (CTX-SNIPPET-VERSION).

Usage:
    uv run tools/i18n_extractor.py extract --src src/ --out messages.pot
    uv run tools/i18n_extractor.py xgettext --src src/ --langs python,cpp --out messages.pot
    uv run tools/i18n_extractor.py jinja --src src/templates --out templates.pot
    uv run tools/i18n_extractor.py enrich --pot messages.pot
    uv run tools/i18n_extractor.py validate --src src/
"""

import ast
import subprocess
from pathlib import Path
from typing import Final

import polib
import typer
from rich.console import Console

CONTEXT_MAX_LINES = 10  # max lines to expand in each direction around a string
console = Console()

# @TRANSLATOR marker: human note in source -> xgettext --add-comments -> #. line.
# Literal is duplicated in i18n_translator.py (_extract_translator_notes); keep in sync.
TRANSLATOR_TAG: Final = "@TRANSLATOR"

# xgettext language flag per file extension
LANG_MAP = {
    ".py": "Python",
    ".js": "JavaScript",  # qooxdoo frontend
    ".ts": "JavaScript",  # rocket frontend; xgettext has no TypeScript language
    ".tsx": "JavaScript",
    ".jsx": "JavaScript",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C++",
    ".rc": "C++",  # STRINGTABLE entries; xgettext treats .rc as C-like
}

# xgettext --keyword flags: single source of truth for run_xgettext()'s cmd, mapped
# to the language(s)/tool that call each translation function.
XGETTEXT_KEYWORDS: Final[dict[str, str]] = {
    "_": "Python",
    "gettext": "Python",
    "user_message": "Python (osparc)",
    "tr": "Qt/MFC C++, qooxdoo JS",
    "t": "rocket JS/TS",
    "QT_TR_NOOP": "Qt no-op marker (C++)",
}

# Subset of XGETTEXT_KEYWORDS that Python code can actually call; used only by the
# Python AST-based validate_no_fstring_translations() (never scans .js/.cpp files).
PYTHON_TRANSLATION_FUNC_NAMES: Final[set[str]] = {"_", "gettext", "user_message"}
assert set(XGETTEXT_KEYWORDS) >= PYTHON_TRANSLATION_FUNC_NAMES  # nosec


# ---------------------------------------------------------------------------
# Step 1: xgettext
# ---------------------------------------------------------------------------


def run_xgettext(src_files: list[Path], out_pot: Path) -> bool:
    """
    Run xgettext over all source files in one invocation.
    Returns True on success.
    """
    if not src_files:
        console.print("[extract] No source files found.")
        return False

    cmd = [
        # Extract translatable strings from given input files
        # SEE https://www.gnu.org/software/gettext/manual/html_node/xgettext-Invocation.html
        "xgettext",
        *(f"--keyword={keyword}" for keyword in XGETTEXT_KEYWORDS),
        f"--add-comments={TRANSLATOR_TAG}",
        "--from-code=UTF-8",
        "--output",
        str(out_pot),
        "--package-name=osparc-simcore",
        "--msgid-bugs-address=",
        # SUGGESTION: remove --no-location if you want
    ]

    # xgettext needs --language per file; pass each file with its language.
    # Group files by language to avoid per-file subprocess overhead.
    by_lang: dict[str, list[Path]] = {}
    for f in src_files:
        lang = LANG_MAP.get(f.suffix.lower())
        if lang:
            by_lang.setdefault(lang, []).append(f)
        else:
            console.print(f"  [skip] unsupported extension: {f}")

    if not by_lang:
        console.print("[extract] No files with supported extensions.")
        return False

    first = True
    for lang, files in by_lang.items():
        batch_cmd = [*cmd, f"--language={lang}", *(str(f) for f in files)]
        if not first:
            # append to the .pot produced by the first batch
            batch_cmd.append("--join-existing")
        first = False

        result = subprocess.run(batch_cmd, capture_output=True, text=True, check=False)  # noqa: S603
        if result.returncode != 0:
            console.print(f"[xgettext ERROR] {result.stderr.strip()}")
            return False
        console.print(f"  [xgettext] {lang}: {len(files)} file(s)")

    return True


# ---------------------------------------------------------------------------
# Step 1b: Babel extraction for Jinja2 templates
# ---------------------------------------------------------------------------
#
# xgettext cannot parse Jinja2 ({% trans %} blocks, {{ gettext(...) }} calls),
# so Babel's jinja2.ext.babel_extract is used for *.j2 templates. The output is
# a polib .pot with the same #: filepath:lineno references that `enrich` and
# `msgcat` (in the Makefile `merge` step) consume, so it slots into the existing
# pipeline unchanged.

_JINJA_METHOD_MAP = [("**.j2", "jinja2.ext.babel_extract")]
# i18n extension is auto-loaded by babel_extract; encoding pinned to UTF-8.
_JINJA_OPTIONS_MAP = {"**.j2": {"encoding": "utf-8", "silent": "false"}}


def run_babel_jinja(src_dir: Path, out_pot: Path) -> bool:
    """Extract translatable strings from Jinja2 templates under *src_dir*.

    Returns True on success. Occurrence paths are recorded relative to the
    given *src_dir* prefix so they resolve from the repo root (matching the
    xgettext step), which lets `enrich` locate the source snippets.
    """
    from babel.messages.extract import extract_from_dir  # noqa: PLC0415

    # (msgid, msgid_plural, context) -> POEntry, so repeated strings merge
    # into one entry carrying multiple #: occurrences.
    entries: dict[tuple[str, str | None, str | None], polib.POEntry] = {}

    for filename, lineno, message, _comments, context in extract_from_dir(
        dirname=src_dir,
        method_map=_JINJA_METHOD_MAP,
        options_map=_JINJA_OPTIONS_MAP,
    ):
        if isinstance(message, tuple | list):
            msgid, msgid_plural = message[0], message[1]
        else:
            msgid, msgid_plural = message, None

        if not msgid:
            continue

        msgctxt = context or None
        key = (msgid, msgid_plural, msgctxt)
        occurrence = (f"{src_dir}/{filename}", str(lineno))

        if key in entries:
            entries[key].occurrences.append(occurrence)
            continue

        if msgid_plural:
            entry = polib.POEntry(
                msgid=msgid,
                msgid_plural=msgid_plural,
                msgstr_plural={0: "", 1: ""},
                msgctxt=msgctxt,
                occurrences=[occurrence],
            )
        else:
            entry = polib.POEntry(
                msgid=msgid,
                msgstr="",
                msgctxt=msgctxt,
                occurrences=[occurrence],
            )
        entries[key] = entry

    pot = polib.POFile(wrapwidth=0)
    pot.metadata = {
        "Project-Id-Version": "osparc-simcore",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
    }
    for entry in entries.values():
        pot.append(entry)

    out_pot.parent.mkdir(parents=True, exist_ok=True)
    pot.save(str(out_pot))
    console.print(f"  [jinja] {len(pot)} entry/ies -> {out_pot}")
    return True


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def validate_no_fstring_translations(src_files: list[Path]) -> bool:  # noqa: C901
    """Fail when translation calls use f-strings as msgids."""
    violations: list[tuple[Path, int, str]] = []

    for path in src_files:
        if path.suffix.lower() != ".py":
            continue

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as err:
            console.print(f"  [warn] skipping syntax-invalid file {path}: {err}")
            continue

        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            call_name = _call_name(node.func)
            if call_name not in PYTHON_TRANSLATION_FUNC_NAMES:
                continue

            if not node.args:
                continue

            if isinstance(node.args[0], ast.JoinedStr):
                lineno = node.lineno
                line_text = lines[lineno - 1].strip() if 0 < lineno <= len(lines) else ""
                violations.append((path, lineno, line_text))

    if not violations:
        return True

    console.print("[extract ERROR] Disallowed f-strings in translation calls:")
    for path, lineno, line_text in violations:
        console.print(f"  [error] {path}:{lineno}: use user_message('template {{name}}').format(name=...)")
        if line_text:
            console.print(f"          {line_text}")

    console.print(f"[extract ERROR] Found {len(violations)} violation(s).")
    return False


def _extract_hints_from_file(path: Path) -> dict[str, str]:
    """Return {msgid: hint} from ``user_message(_hint=...)`` calls in a single Python file."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as err:
        console.print(f"  [warn] skipping syntax-invalid file {path}: {err}")
        return {}

    hints: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node.func) != "user_message":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        msgid = node.args[0].value
        if not isinstance(msgid, str):
            continue

        for kw in node.keywords:
            if kw.arg == "_hint" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                hints[msgid] = kw.value.value
                break

    return hints


def collect_python_hints(src_files: list[Path]) -> dict[str, str]:
    """Scan Python source files and return {msgid: hint} from ``user_message(_hint=...)`` calls.

    Only plain string literals are accepted for both ``msg`` and ``_hint``
    (f-strings are already rejected by ``validate_no_fstring_translations``).
    When the same msgid appears with different hints, the first one wins and a
    warning is emitted.
    """
    hints: dict[str, str] = {}

    for path in src_files:
        if path.suffix.lower() != ".py":
            continue

        for msgid, hint in _extract_hints_from_file(path).items():
            if msgid in hints and hints[msgid] != hint:
                console.print(f"  [warn] {path}: duplicate _hint for msgid {msgid!r} (keeping first occurrence)")
            else:
                hints[msgid] = hint

    return hints


# ---------------------------------------------------------------------------
# Step 2: enrich with extractor-owned context metadata
# ---------------------------------------------------------------------------
#
# These markers are written by the extractor step (this script), not by xgettext.
# They use the CTX- prefix to stay distinct from the @TRANSLATOR prefix that
# xgettext captures via --add-comments=@TRANSLATOR (xgettext command).
#
#   @TRANSLATOR ...      →  human note in source code → extracted by xgettext → #. line
#   CTX-SNIPPET:         → machine-generated by enrich
#   CTX-SNIPPET-VERSION: → git-blame hash for the referenced line
#   CTX-INTERPRETATION:  → written by i18n_translator.py
#   CTX-VERSION:         → translation/version stamp by i18n_translator.py


def get_blame_commit(filepath: str, lineno: int, cwd: Path | None = None) -> str:
    """Return short commit hash for file:line, or 'unknown' when unavailable."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "blame", "-L", f"{lineno},{lineno}", "--porcelain", filepath],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        first_line = result.stdout.splitlines()[0]
        return first_line.split()[0][:7]
    except Exception:
        return "unknown"


def parse_ctx_comment(comment: str) -> tuple[list[str], dict[str, str], list[str]]:
    """Split comment block into non-CTX lines, CTX scalar fields, and snippet lines."""
    passthrough_lines: list[str] = []
    ctx_fields: dict[str, str] = {}
    snippet_lines: list[str] = []
    in_snippet = False

    for raw_line in comment.splitlines():
        line = raw_line.strip()
        if line.startswith("CTX-SNIPPET:"):
            in_snippet = True
            continue
        if line.startswith("CTX-") and ":" in line:
            in_snippet = False
            key, value = line.split(":", 1)
            ctx_fields[key.strip()] = value.strip()
            continue
        if in_snippet:
            snippet_lines.append(line)
        else:
            passthrough_lines.append(raw_line)

    return passthrough_lines, ctx_fields, snippet_lines


def render_ctx_comment(passthrough_lines: list[str], ctx_fields: dict[str, str], snippet_lines: list[str]) -> str:
    """Render comment preserving non-CTX lines while canonicalizing CTX layout."""
    ordered_lines = [line for line in passthrough_lines if line.strip() != ""]

    ordered_lines.append("CTX-SNIPPET:")
    ordered_lines.extend(snippet_lines)

    ordered_keys = ["CTX-SNIPPET-VERSION", "CTX-INTERPRETATION", "CTX-VERSION"]
    seen = set()
    for key in ordered_keys:
        value = ctx_fields.get(key)
        if value:
            ordered_lines.append(f"{key}: {value}")
            seen.add(key)

    # Preserve any additional CTX-* fields that might have been added later.
    ordered_lines.extend(f"{key}: {ctx_fields[key]}" for key in sorted(k for k in ctx_fields if key_not_seen(k, seen)))

    return "\n".join(ordered_lines).strip()


def key_not_seen(key: str, seen: set[str]) -> bool:
    return key.startswith("CTX-") and key not in seen and key != "CTX-SNIPPET"


def _snippet_bounds(lines: list[str], lineno: int, max_context: int = CONTEXT_MAX_LINES) -> tuple[int, int]:
    """Return a 0-based inclusive (start, end) line range around lineno (1-based).

    Expands to the enclosing block instead of a fixed window: walks upward/downward
    while sibling lines share the same or deeper indentation, stopping at the first
    blank line or shallower-indented line (the block's natural boundary, e.g. the
    enclosing `def`/JSX tag). Bounded by max_context lines in each direction so
    prompts stay small even inside large blocks.
    """
    idx = lineno - 1
    target_indent = len(lines[idx]) - len(lines[idx].lstrip())
    min_start = max(0, idx - max_context)
    max_end = min(len(lines) - 1, idx + max_context)

    start = idx
    while start > min_start:
        prev_line = lines[start - 1]
        start -= 1
        if not prev_line.strip() or (len(prev_line) - len(prev_line.lstrip())) < target_indent:
            break

    end = idx
    while end < max_end:
        next_line = lines[end + 1]
        if not next_line.strip() or (len(next_line) - len(next_line.lstrip())) < target_indent:
            break
        end += 1

    return start, end


def enrich(pot_path: Path, repo_root: Path, py_hints: dict[str, str] | None = None) -> None:
    """
    Step 2: read the .pot produced by xgettext, add extractor-owned CTX metadata
    to each entry from source locations in #: filepath:lineno.

    Ownership contract:
        - enrich writes only CTX-SNIPPET and CTX-SNIPPET-VERSION
        - translator writes CTX-INTERPRETATION and CTX-VERSION

    CTX-* fields are stored in tcomment (# lines), not comment (#. lines).

    ``py_hints`` maps msgid → translator hint string collected from
    ``user_message(_hint=...)`` calls.  When a hint is present and not already
    in the entry's ``#.`` comment block, ``@TRANSLATOR <hint>`` is prepended.
    """
    po = polib.pofile(str(pot_path), wrapwidth=0)  # wrapwidth=0: no line-wrapping
    # wrapping breaks multi-word
    # snippet lines across #. lines

    # Collect _hint values from Python source files referenced in the pot.
    # Files are resolved relative to repo_root, matching how #: references are recorded.
    if py_hints is None:
        py_files = sorted(
            {repo_root / filepath for entry in po for filepath, _ in entry.occurrences if filepath.endswith(".py")}
        )
        py_hints = collect_python_hints([f for f in py_files if f.exists()])
        if py_hints:
            console.print(f"  [hints] {len(py_hints)} _hint value(s) collected from Python sources")

    hints = py_hints

    for entry in po:
        if not entry.occurrences:
            continue

        filepath, lineno_str = entry.occurrences[0]
        try:
            lineno = int(lineno_str)
        except ValueError:
            continue

        abs_path = repo_root / filepath
        if not abs_path.exists():
            console.print(f"  [warn] not found: {abs_path}")
            continue

        lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
        start, end = _snippet_bounds(lines, lineno)

        snippet_lines = [f"  {'>>>' if i + 1 == lineno else '   '} {lines[i]}" for i in range(start, end + 1)]

        snippet_version = get_blame_commit(filepath, lineno, cwd=repo_root)

        # Inject @TRANSLATOR hint from _hint kwarg if not already present.
        hint = hints.get(entry.msgid)
        if hint:
            at_translator_line = f"{TRANSLATOR_TAG} {hint}"
            existing = entry.comment or ""
            if at_translator_line not in existing:
                entry.comment = (at_translator_line + "\n" + existing).strip()

        # entry.comment (#. lines) is left untouched -- it holds @TRANSLATOR notes.
        passthrough, ctx_fields, _ = parse_ctx_comment(entry.tcomment or "")
        ctx_fields["CTX-SNIPPET-VERSION"] = snippet_version
        entry.tcomment = render_ctx_comment(passthrough, ctx_fields, snippet_lines)

    # Ensure enriched POT keeps UTF-8 metadata for non-ASCII msgids/comments.
    po.encoding = "utf-8"
    po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    po.metadata["Content-Transfer-Encoding"] = "8bit"
    po.save(str(pot_path))
    console.print(f"[enrich] {len(po)} entries enriched -> {pot_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def collect_sources(src_dir: Path, langs: list[str] | None) -> list[Path]:
    """Return all source files under src_dir, optionally filtered by language."""
    allowed_exts: set[str] = set()
    if langs:
        lang_to_exts = {
            "python": {".py"},
            "javascript": {".js"},  # qooxdoo frontend
            "cpp": {".cpp", ".cxx", ".cc", ".h"},
            "c": {".c", ".h"},
            "mfc": {".rc", ".cpp", ".h"},
        }
        for lang in langs:
            allowed_exts |= lang_to_exts.get(lang.lower(), set())
    else:
        allowed_exts = set(LANG_MAP.keys())

    files = [f for f in sorted(src_dir.rglob("*")) if f.suffix.lower() in allowed_exts]
    console.print(f"[collect] {len(files)} file(s) under {src_dir}")
    return files


def ensure_xgettext_available() -> None:
    # Check xgettext is available
    if subprocess.run(["which", "xgettext"], capture_output=True, check=False).returncode != 0:  # noqa: S607
        msg = (
            "[error] xgettext not found. Install via:\n"
            "  apt install gettext   # Debian/Ubuntu\n"
            "  brew install gettext  # macOS"
        )
        raise typer.Exit(msg)


app = typer.Typer(
    add_completion=False,
    help="Extract strings with xgettext and enrich .pot entries with CTX-* metadata.",
    no_args_is_help=True,
)


def run_xgettext_step(src: Path, out: Path, langs: str | None) -> None:
    """Shared implementation for xgettext."""
    ensure_xgettext_available()

    lang_list = [lang.strip() for lang in langs.split(",")] if langs else None
    src_files = collect_sources(src, lang_list)
    if not src_files:
        raise typer.Exit(code=1)

    if not run_xgettext(src_files, out):
        raise typer.Exit(code=1)

    if not validate_no_fstring_translations(src_files):
        raise typer.Exit(code=1)

    console.print(f"[done] xgettext -> {out}")


def run_validate_step(src: Path, langs: str | None) -> None:
    """Shared implementation for validation-only checks."""
    lang_list = [lang.strip() for lang in langs.split(",")] if langs else None
    src_files = collect_sources(src, lang_list)
    if not src_files:
        raise typer.Exit(code=1)

    if not validate_no_fstring_translations(src_files):
        raise typer.Exit(code=1)

    console.print("[done] validate -> no disallowed translation f-strings found")


def run_enrich_step(pot: Path, repo_root: Path) -> None:
    """Shared implementation for enrich."""
    if not pot.exists():
        console.print(f"[error] .pot not found: {pot}")
        raise typer.Exit(code=1)

    enrich(pot, repo_root)
    console.print(f"[done] enrich -> {pot}")


def run_xgettext_cmd(src: Path, out: Path, langs: str | None) -> None:
    """Run only xgettext extraction over source files."""
    run_xgettext_step(src=src, out=out, langs=langs)


def run_enrich_cmd(pot: Path, repo_root: Path) -> None:
    """Run only enrichment on an existing POT catalog."""
    run_enrich_step(pot=pot, repo_root=repo_root)


@app.command("xgettext")
def xgettext_cmd(
    src: Path = typer.Option(Path("src"), help="Source directory"),
    out: Path = typer.Option(Path("messages.pot"), help="Output .pot file"),
    langs: str | None = typer.Option(
        None,
        help="Comma-separated languages to extract: python,cpp,c,mfc (default: all)",
    ),
) -> None:
    """Run only xgettext extraction."""
    run_xgettext_cmd(src=src, out=out, langs=langs)


@app.command("jinja")
def jinja_cmd(
    src: Path = typer.Option(Path("src"), help="Directory to scan for *.j2 templates"),
    out: Path = typer.Option(Path("templates.pot"), help="Output .pot file"),
) -> None:
    """Extract translatable strings from Jinja2 templates via Babel."""
    if not src.is_dir():
        console.print(f"[error] source directory not found: {src}")
        raise typer.Exit(code=1)
    if not run_babel_jinja(src, out):
        raise typer.Exit(code=1)
    console.print(f"[done] jinja -> {out}")


@app.command("enrich")
def enrich_cmd(
    pot: Path = typer.Option(Path("messages.pot"), help="Existing .pot file to enrich"),
    repo_root: Path = typer.Option(
        Path(),
        help="Repo root for resolving source paths in #: references",
    ),
) -> None:
    """Run only CTX snippet enrichment on an existing .pot."""
    run_enrich_cmd(pot=pot, repo_root=repo_root)


@app.command("extract")
def extract(
    src: Path = typer.Option(Path("src"), help="Source directory"),
    out: Path = typer.Option(Path("messages.pot"), help="Output .pot file"),
    repo_root: Path = typer.Option(
        Path(),
        help="Repo root for resolving source paths in #: references",
    ),
    langs: str | None = typer.Option(
        None,
        help="Comma-separated languages to extract: python,cpp,c,mfc (default: all)",
    ),
) -> None:
    """Run xgettext then enrich."""
    run_xgettext_cmd(src=src, out=out, langs=langs)
    run_enrich_cmd(pot=out, repo_root=repo_root)


@app.command("validate")
def validate_cmd(
    src: Path = typer.Option(Path("src"), help="Source directory"),
    langs: str | None = typer.Option(
        None,
        help="Comma-separated languages to scan: python,cpp,c,mfc (default: all)",
    ),
) -> None:
    """Run validation checks only (no catalog generation)."""
    run_validate_step(src=src, langs=langs)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
