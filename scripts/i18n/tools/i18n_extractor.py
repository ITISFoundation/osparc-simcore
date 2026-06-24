# /// script
# requires-python = ">=3.11"
# dependencies = [
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

    Step 2 — enrich: for each entry, read #: references to load
                     surrounding source lines (CTX-SNIPPET) and write a
             extractor-owned snippet freshness marker (CTX-SNIPPET-VERSION).

Usage:
    uv run tools/i18n_extractor.py extract --src src/ --out messages.pot
    uv run tools/i18n_extractor.py xgettext --src src/ --langs python,cpp --out messages.pot
    uv run tools/i18n_extractor.py enrich --pot messages.pot
    uv run tools/i18n_extractor.py validate --src src/
"""

import ast
import subprocess
from pathlib import Path

import polib
import typer
from rich.console import Console

CONTEXT_LINES = 6  # source lines captured around each string
console = Console()

# xgettext language flag per file extension
LANG_MAP = {
    ".py": "Python",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cc": "C++",
    ".c": "C",
    ".h": "C++",
    ".rc": "C++",  # STRINGTABLE entries; xgettext treats .rc as C-like
}

TRANSLATION_FUNC_NAMES = {
    "_",
    "user_message",  # osparc
    "gettext",
    "tr",
    "QT_TR_NOOP",
}


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
        "xgettext",
        "--keyword=_",
        "--keyword=gettext",
        "--keyword=user_message",  # osparc marker
        "--keyword=tr",  # Qt / MFC
        "--keyword=QT_TR_NOOP",  # Qt no-op marker
        "--add-comments=@TRANSLATOR",
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
            if call_name not in TRANSLATION_FUNC_NAMES:
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
        console.print(f"  [error] {path}:{lineno}: use _('template {{name}}').format(name=...)")
        if line_text:
            console.print(f"          {line_text}")

    console.print(f"[extract ERROR] Found {len(violations)} violation(s).")
    return False


# ---------------------------------------------------------------------------
# Step 2: enrich with extractor-owned context metadata
# ---------------------------------------------------------------------------
#
# These markers are written by the extractor step (this script), not by xgettext.
# They use the CTX- prefix to stay distinct from the @TRANSLATOR prefix that
# xgettext captures via --add-comments=@TRANSLATOR (xgettext command).
#
#   @TRANSLATOR ...  →  human note in source code → extracted by xgettext → #. line
#   CTX-SNIPPET:         → machine-generated by enrich
#   CTX-SNIPPET-VERSION: → git-blame hash for the referenced line
#   CTX-INTERPRETATION:  → written by i18n_translator.py
#   CTX-VERSION:         → translation/version stamp by i18n_translator.py


def get_blame_commit(filepath: str, lineno: int) -> str:
    """Return short commit hash for file:line, or 'unknown' when unavailable."""
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "blame", "-L", f"{lineno},{lineno}", "--porcelain", filepath],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
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


def enrich(pot_path: Path, repo_root: Path) -> None:
    """
    Step 2: read the .pot produced by xgettext, add extractor-owned CTX metadata
    to each entry from source locations in #: filepath:lineno.

    Ownership contract:
        - enrich writes only CTX-SNIPPET and CTX-SNIPPET-VERSION
        - translator writes CTX-INTERPRETATION and CTX-VERSION

    CTX-* fields are stored in tcomment (# lines), not comment (#. lines).
    """
    po = polib.pofile(str(pot_path), wrapwidth=0)  # wrapwidth=0: no line-wrapping
    # wrapping breaks multi-word
    # snippet lines across #. lines

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
        start = max(0, lineno - CONTEXT_LINES // 2 - 1)
        end = min(len(lines), lineno + CONTEXT_LINES // 2)

        snippet_lines = [f"  {'>>>' if i + 1 == lineno else '   '} {lines[i]}" for i in range(start, end)]

        snippet_version = get_blame_commit(filepath, lineno)

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
