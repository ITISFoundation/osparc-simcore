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

    Step 1c — json: extract translatable string values from JSON resource
                     files (e.g. frontend guided tours) by key. These strings
                     are data loaded at runtime, not literal tr()/gettext()
                     calls, so neither xgettext nor Babel can see them.
                     Extraction is line-based (one "key": "value" pair per
                     line), which yields exact #: filepath:lineno references
                     and lets json.loads() handle string unescaping.

    Step 1d — ts-ast: extract t()/tr() calls from .js/.jsx/.ts/.tsx files via the
                     TypeScript compiler API (a small embedded Node script), not
                     xgettext -- xgettext's `--language=JavaScript` mode has no real
                     JSX/TypeScript support and silently truncates parsing mid-file
                     on certain JSX constructs. Requires `--node-cwd <dir>` (a
                     directory whose node_modules contains `typescript`) whenever
                     --src contains any of those extensions.

    Step 2 — enrich: for each entry, read #: references to load
                     surrounding source lines (CTX-SNIPPET) and write a
             extractor-owned snippet freshness marker (CTX-SNIPPET-VERSION).

Usage:
    uv run tools/i18n_extractor.py extract --src src/ --out messages.pot
    uv run tools/i18n_extractor.py xgettext --src src/ --langs python,cpp --out messages.pot
    uv run tools/i18n_extractor.py xgettext --src ui/src --out ui.pot --node-cwd ui/
    uv run tools/i18n_extractor.py jinja --src src/templates --out templates.pot
    uv run tools/i18n_extractor.py json --src src/resource/tours --keys name,description,title,text --out tours.pot
    uv run tools/i18n_extractor.py enrich --pot messages.pot
    uv run tools/i18n_extractor.py validate --src src/
"""

import ast
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Final

import polib
import typer
from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.theme import Theme

CONTEXT_MAX_LINES = 10  # max lines to expand in each direction around a string


# @TRANSLATOR marker: human note in source -> xgettext --add-comments -> #. line.
# Literal is duplicated in i18n_translator.py (_extract_translator_notes); keep in sync.
TRANSLATOR_TAG: Final = "@TRANSLATOR"

# ---------------------------------------------------------------------------
# Step 1a: xgettext extraction for source files (Python, C++, MFC .rc)
# ---------------------------------------------------------------------------


class XgetextExtractor:
    """Extract translatable strings from source files using GNU xgettext.

    Files are grouped by language to minimize subprocess invocations.
    SEE https://www.gnu.org/software/gettext/manual/html_node/xgettext-Invocation.html
    """

    # xgettext --language flag per file extension (case-insensitive match).
    # \note .js/.jsx/.ts/.tsx are deliberately NOT listed here anymore -- xgettext's
    # `--language=JavaScript` mode has no real JSX/TypeScript support and has a
    # confirmed defect where certain constructs inside a JSX expression container
    # silently truncate parsing for the rest of the file (see TS_AST_EXTRACTOR_EXTS /
    # TypeScriptAstExtractor below, which handles those extensions instead).
    LANG_MAP: Final[dict[str, str]] = {
        ".py": "Python",
        ".cpp": "C++",
        ".cxx": "C++",
        ".cc": "C++",
        ".c": "C",
        ".h": "C++",
        ".rc": "C++",  # STRINGTABLE entries; xgettext treats .rc as C-like
    }

    # --keyword flags: single source of truth for all translation functions xgettext
    # itself is invoked for (Python/C++/MFC). JS/TS keywords ("t"/"tr") are handled by
    # TypeScriptAstExtractor's own KEYWORDS set below, not by xgettext anymore.
    KEYWORDS: Final[dict[str, str]] = {
        "_": "Python",
        "gettext": "Python",
        "user_message": "Python (osparc)",
        "tr": "Qt/MFC C++",
        "QT_TR_NOOP": "Qt no-op marker (C++)",
    }

    def run(self, src_files: list[Path], out_pot: Path) -> bool:
        """Returns True on success."""
        if not src_files:
            console.print("[extract] No source files found.")
            return False

        base_cmd = [
            "xgettext",
            *(f"--keyword={kw}" for kw in self.KEYWORDS),
            f"--add-comments={TRANSLATOR_TAG}",
            "--from-code=UTF-8",
            "--output",
            str(out_pot),
            "--package-name=osparc-simcore",
            "--msgid-bugs-address=",
        ]

        # Group files by language to batch invocations.
        by_lang: dict[str, list[Path]] = {}
        for f in src_files:
            lang = self.LANG_MAP.get(f.suffix.lower())
            if lang:
                by_lang.setdefault(lang, []).append(f)
            else:
                console.print(f"  [skip] unsupported extension: {f}")

        if not by_lang:
            console.print("[extract] No files with supported extensions.")
            return False

        first = True
        for lang, files in by_lang.items():
            batch_cmd = [*base_cmd, f"--language={lang}", *(str(f) for f in files)]
            if not first:
                batch_cmd.append("--join-existing")  # append to the .pot from first batch
            first = False

            result = subprocess.run(batch_cmd, capture_output=True, text=True, check=False)  # noqa: S603
            if result.returncode != 0:
                console.print(f"[xgettext ERROR] {result.stderr.strip()}")
                return False
            console.print(f"  [xgettext] {lang}: {len(files)} file(s)")

        return True


# Subset of XgetextExtractor.KEYWORDS that Python code can actually call; used only by the
# Python AST-based validate_no_fstring_translations() (never scans .js/.cpp files).
PYTHON_TRANSLATION_FUNC_NAMES: Final[set[str]] = {"_", "gettext", "user_message"}
assert XgetextExtractor.KEYWORDS.keys() >= PYTHON_TRANSLATION_FUNC_NAMES  # nosec


# ---------------------------------------------------------------------------
# Step 1d: TypeScript-compiler-API extraction for JS/TS/JSX/TSX files
# ---------------------------------------------------------------------------
#
# xgettext's `--language=JavaScript` mode has no real JSX/TypeScript support: it has
# a confirmed defect where certain constructs inside a JSX expression container (a
# template literal, or a block-bodied arrow function returning JSX) silently
# truncate parsing for the REST of that source file -- no error, exit code 0, just
# silently missing translations. This extractor replaces xgettext entirely for
# .js/.jsx/.ts/.tsx by shelling out to a small Node script that uses the real
# TypeScript compiler API (a spec-correct JSX/TSX parser) to find translation calls.
TS_AST_EXTRACTOR_EXTS: Final[frozenset[str]] = frozenset({".js", ".jsx", ".ts", ".tsx"})

# Embedded as a string (not a separate fetched file) so this stays a single,
# self-contained pinned script, consistent with the rest of this file. Written to a
# `.cjs` tempfile before running so it's always treated as CommonJS regardless of the
# target project's package.json "type" field.
_TS_AST_EXTRACTOR_JS: Final[str] = r"""
"use strict";
const fs = require("fs");
const path = require("path");
const { createRequire } = require("module");

const [, , srcDirArg, ...fileArgs] = process.argv;
const srcDir = path.resolve(srcDirArg);

// Module resolution for require() is relative to *this* file's own (tempfile)
// location, not process.cwd() -- createRequire seeded from a package.json in the
// target project's directory (passed as cwd by the Python caller) is what makes
// `require("typescript")` resolve the CALLER's node_modules/typescript.
const req = createRequire(path.join(process.cwd(), "package.json"));
const ts = req("typescript");

const KEYWORDS = new Set(["t", "tr"]);
const results = [];

function scriptKindFor(file) {
  const ext = path.extname(file).toLowerCase();
  if (ext === ".tsx") return ts.ScriptKind.TSX;
  if (ext === ".ts") return ts.ScriptKind.TS;
  if (ext === ".jsx") return ts.ScriptKind.JSX;
  return ts.ScriptKind.JS;
}

// Heuristic (not full JSX-comment AST attachment): matches the @TRANSLATOR
// convention used in this codebase, e.g. `{/* @TRANSLATOR: ... */}` immediately
// followed (only whitespace in between) by the `t(...)`/`tr(...)` call.
function findTranslatorComment(text, callStart) {
  const before = text.slice(0, callStart);
  const idx = before.lastIndexOf("{/*");
  if (idx === -1) return null;
  const closeIdx = text.indexOf("*/}", idx);
  if (closeIdx === -1 || closeIdx >= callStart) return null;
  const between = text.slice(closeIdx + 3, callStart);
  // allow the JSX expression container's own opening "{" between the comment
  // and the call (e.g. "{/* ... */}\n      {t(...)}") in addition to whitespace.
  if (!/^[\s{]*$/.test(between)) return null;
  const m = /@TRANSLATOR:?\s*([\s\S]*?)\s*\*\/\}$/.exec(text.slice(idx, closeIdx + 3));
  return m ? m[1].trim() : null;
}

for (const file of fileArgs) {
  const text = fs.readFileSync(file, "utf8");
  const sourceFile = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, scriptKindFor(file));
  const rel = path.relative(srcDir, file).split(path.sep).join("/");

  // Matches a bare call `t(...)` as well as a property-access call `i18n.t(...)`/
  // `this.t(...)` -- xgettext's --keyword matching isn't identifier-qualifier-aware
  // either, so this preserves parity with what the old xgettext-based pipeline used
  // to catch (e.g. dockviewLayout.ts's `i18n.t(...)` calls).
  function calleeKeyword(expr) {
    if (ts.isIdentifier(expr)) return expr.text;
    if (ts.isPropertyAccessExpression(expr) && ts.isIdentifier(expr.name)) return expr.name.text;
    return null;
  }

  const visit = (node) => {
    if (
      ts.isCallExpression(node) &&
      KEYWORDS.has(calleeKeyword(node.expression)) &&
      node.arguments.length > 0 &&
      ts.isStringLiteralLike(node.arguments[0])
    ) {
      const argStart = node.arguments[0].getStart(sourceFile);
      const { line } = sourceFile.getLineAndCharacterOfPosition(argStart);
      results.push({
        file: rel,
        line: line + 1,
        msgid: node.arguments[0].text,
        translatorComment: findTranslatorComment(text, node.getStart(sourceFile)),
      });
    }
    ts.forEachChild(node, visit);
  };

  visit(sourceFile);
}

process.stdout.write(JSON.stringify(results));
"""


class TypeScriptAstExtractor:
    """Extract t()/tr() calls from JS/TS/JSX/TSX files via the TypeScript compiler API.

    Runs a small embedded Node script (_TS_AST_EXTRACTOR_JS) instead of xgettext's
    JavaScript mode -- a real, spec-correct JSX/TSX parser that cannot suffer the
    silent-truncation defect xgettext has. `node_cwd` must be a directory whose
    `node_modules` contains `typescript` (i.e. the frontend project root): module
    resolution for `require()` is relative to the *process cwd*'s package.json, not
    this script's own (temp-file) location, which is why `node_cwd` is required.
    """

    def run(
        self, src_files: list[Path], out_pot: Path, src_dir: Path, node_cwd: Path, *, merge_into_existing: bool
    ) -> bool:
        """Returns True on success.

        ``merge_into_existing`` must be True only when out_pot was FRESHLY written by
        XgetextExtractor earlier in the SAME `run_xgettext_step` call (Python/C++ files
        in the same --src tree); it must be False otherwise (a stale out_pot may exist
        on disk from a PREVIOUS, unrelated invocation of this command and must not be
        used as a merge base -- doing so would silently accumulate stale #: occurrences
        for files/lines that may no longer exist).
        """
        if not src_files:
            console.print("[ts-ast] No source files found.")
            return False

        with tempfile.NamedTemporaryFile("w", suffix=".cjs", delete=False) as tmp:
            tmp.write(_TS_AST_EXTRACTOR_JS)
            tmp_path = Path(tmp.name)

        try:
            # Resolve to absolute paths: src_files may be relative to the caller's cwd
            # (e.g. `services/sim4life/ui/src/...`), but the subprocess below runs with
            # cwd=node_cwd (a DIFFERENT directory, needed for require() resolution), so
            # relative paths would otherwise be looked up in the wrong place.
            cmd = [
                "node",
                str(tmp_path),
                str(src_dir.resolve()),
                *(str(f.resolve()) for f in src_files),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=node_cwd)  # noqa: S603
        finally:
            tmp_path.unlink(missing_ok=True)

        if result.returncode != 0:
            console.print(f"[ts-ast ERROR] {result.stderr.strip()}")
            return False

        try:
            matches: list[dict] = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as err:
            console.print(f"[ts-ast ERROR] could not parse extractor output: {err}")
            return False

        # msgid -> POEntry: duplicate strings merge into one entry with multiple #: occurrences.
        entries: dict[str, polib.POEntry] = {}
        for match in matches:
            msgid = match["msgid"]
            occurrence = (f"{src_dir}/{match['file']}", str(match["line"]))
            comment = match.get("translatorComment") or None
            if msgid in entries:
                entries[msgid].occurrences.append(occurrence)
                continue
            entries[msgid] = polib.POEntry(
                msgid=msgid,
                msgstr="",
                occurrences=[occurrence],
                comment=f"{TRANSLATOR_TAG} {comment}" if comment else "",
            )

        if merge_into_existing and out_pot.exists():
            pot = polib.pofile(str(out_pot), wrapwidth=0)
        else:
            pot = polib.POFile(wrapwidth=0)
            pot.metadata = {
                "Project-Id-Version": "osparc-simcore",
                "Content-Type": "text/plain; charset=UTF-8",
                "Content-Transfer-Encoding": "8bit",
            }

        for msgid, entry in entries.items():
            existing = pot.find(msgid)
            if existing is not None:
                existing.occurrences.extend(entry.occurrences)
                continue
            pot.append(entry)

        out_pot.parent.mkdir(parents=True, exist_ok=True)
        pot.save(str(out_pot))
        console.print(f"  [ts-ast] {len(entries)} entry/ies from {len(src_files)} file(s) -> {out_pot}")
        return True


# ---------------------------------------------------------------------------
# Step 1b: Babel extraction for Jinja2 templates
# ---------------------------------------------------------------------------


class BabelJinjaExtractor:
    """Extract translatable strings from Jinja2 templates via Babel.

    xgettext cannot parse Jinja2 ({% trans %} blocks, {{ gettext(...) }} calls),
    so Babel's jinja2.ext.babel_extract is used for *.j2 templates. Output is a
    .pot with the same #: filepath:lineno references that slot into the existing
    pipeline unchanged.
    """

    # i18n extension is auto-loaded by babel_extract; encoding pinned to UTF-8.
    _METHOD_MAP: Final = [("**.j2", "jinja2.ext.babel_extract")]
    _OPTIONS_MAP: Final = {"**.j2": {"encoding": "utf-8", "silent": "false"}}

    def run(self, src_dir: Path, out_pot: Path) -> bool:
        """Returns True on success."""
        from babel.messages.extract import extract_from_dir  # noqa: PLC0415

        # (msgid, msgid_plural, context) -> POEntry, so repeated strings merge
        # into one entry carrying multiple #: occurrences.
        entries: dict[tuple[str, str | None, str | None], polib.POEntry] = {}

        for filename, lineno, message, _comments, context in extract_from_dir(
            dirname=src_dir,
            method_map=self._METHOD_MAP,
            options_map=self._OPTIONS_MAP,
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


# ---------------------------------------------------------------------------
# Step 1c: JSON-value extraction (e.g. frontend guided tours)
# ---------------------------------------------------------------------------


class JsonKeysExtractor:
    """Extract translatable string values from JSON files by key name.

    Targets JSON resource files (e.g. guided tour definitions) whose user-facing
    strings are loaded at runtime and therefore NOT reachable by xgettext (which
    only sees literal tr() calls in .js). Extraction is line-based: every
    translatable "key": "value" pair must be on its own line, yielding exact
    #: filepath:lineno references. Keys not in *keys* (id, anchorEl, ...) are
    wiring and are skipped.
    """

    # Matches one "key": "value" JSON line; `val` is raw-encoded so json.loads() handles escapes.
    KV_LINE_RE: Final[re.Pattern[str]] = re.compile(r'^\s*"(?P<key>[^"]+)"\s*:\s*(?P<val>"(?:[^"\\]|\\.)*")\s*,?\s*$')

    def _collect_entries(
        self,
        src_dir: Path,
        files: list[Path],
        keys: set[str],
    ) -> dict[str, polib.POEntry]:
        # msgid -> POEntry: duplicate strings merge into one entry with multiple #: occurrences.
        entries: dict[str, polib.POEntry] = {}

        for path in files:
            rel = path.relative_to(src_dir)
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for lineno, line in enumerate(lines, start=1):
                match = self.KV_LINE_RE.match(line)
                if not match or match.group("key") not in keys:
                    continue

                try:
                    msgid = json.loads(match.group("val"))
                except json.JSONDecodeError:
                    console.print(f"  [warn] {path}:{lineno}: could not decode JSON value, skipping")
                    continue

                if not msgid:
                    continue

                occurrence = (f"{src_dir}/{rel}", str(lineno))
                if msgid in entries:
                    entries[msgid].occurrences.append(occurrence)
                    continue

                entries[msgid] = polib.POEntry(msgid=msgid, msgstr="", occurrences=[occurrence])

        return entries

    def run(self, src_dir: Path, out_pot: Path, keys: set[str], pattern: str) -> bool:
        """Returns True on success, False when no files match *pattern*."""
        files = sorted(src_dir.rglob(pattern))
        if not files:
            console.print(f"[json] No files matching {pattern!r} under {src_dir}.")
            return False

        entries = self._collect_entries(src_dir, files, keys)

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
        console.print(f"  [json] {len(pot)} entry/ies from {len(files)} file(s) -> {out_pot}")
        return True


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


def _get_name(node: ast.AST) -> str | None:
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

            call_name = _get_name(node.func)
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
        if _get_name(node.func) != "user_message":
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


def _key_not_seen(key: str, seen: set[str]) -> bool:
    return key.startswith("CTX-") and key not in seen and key != "CTX-SNIPPET"


def _render_ctx_comment(passthrough_lines: list[str], ctx_fields: dict[str, str], snippet_lines: list[str]) -> str:
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
    ordered_lines.extend(f"{key}: {ctx_fields[key]}" for key in sorted(k for k in ctx_fields if _key_not_seen(k, seen)))

    return "\n".join(ordered_lines).strip()


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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class _StatusHighlighter(RegexHighlighter):
    highlights: Final = [
        r"(?P<status_done>\[done\])",
        r"(?P<status_error>\[(?:error|[^\]]*ERROR)\])",
        r"(?P<status_warn>\[warn\])",
    ]


console = Console(
    highlighter=_StatusHighlighter(),
    theme=Theme({"status_done": "bold green", "status_error": "bold red", "status_warn": "yellow"}),
    markup=False,  # brackets like [done]/[error] are literal status tags, not Rich markup
)


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
        entry.tcomment = _render_ctx_comment(passthrough, ctx_fields, snippet_lines)

    # Ensure enriched POT keeps UTF-8 metadata for non-ASCII msgids/comments.
    po.encoding = "utf-8"
    po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
    po.metadata["Content-Transfer-Encoding"] = "8bit"
    po.save(str(pot_path))
    console.print(f"[enrich] {len(po)} entries enriched -> {pot_path}")


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
        allowed_exts = set(XgetextExtractor.LANG_MAP.keys()) | TS_AST_EXTRACTOR_EXTS

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


def ensure_node_available() -> None:
    # Check node is available (needed for TypeScriptAstExtractor, i.e. .js/.jsx/.ts/.tsx sources)
    if subprocess.run(["which", "node"], capture_output=True, check=False).returncode != 0:  # noqa: S607
        msg = "[error] node not found. Install Node.js: https://nodejs.org/"
        raise typer.Exit(msg)


app = typer.Typer(
    add_completion=False,
    help="Extract strings with xgettext and enrich .pot entries with CTX-* metadata.",
    no_args_is_help=True,
)


def run_xgettext_step(src: Path, out: Path, langs: str | None, node_cwd: Path | None = None) -> None:
    """Shared implementation for xgettext."""
    lang_list = [lang.strip() for lang in langs.split(",")] if langs else None
    src_files = collect_sources(src, lang_list)
    if not src_files:
        raise typer.Exit(code=1)

    xgettext_files = [f for f in src_files if f.suffix.lower() in XgetextExtractor.LANG_MAP]
    ts_files = [f for f in src_files if f.suffix.lower() in TS_AST_EXTRACTOR_EXTS]

    if not xgettext_files and not ts_files:
        console.print("[extract] No files with supported extensions.")
        raise typer.Exit(code=1)

    if xgettext_files:
        ensure_xgettext_available()
        if not XgetextExtractor().run(xgettext_files, out):
            raise typer.Exit(code=1)

    if ts_files:
        if node_cwd is None:
            console.print(
                "[error] --node-cwd is required to extract .js/.jsx/.ts/.tsx files "
                "(must be a directory whose node_modules contains 'typescript')"
            )
            raise typer.Exit(code=1)
        ensure_node_available()
        if not TypeScriptAstExtractor().run(ts_files, out, src, node_cwd, merge_into_existing=bool(xgettext_files)):
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


def run_xgettext_cmd(src: Path, out: Path, langs: str | None, node_cwd: Path | None = None) -> None:
    """Run only xgettext extraction over source files."""
    run_xgettext_step(src=src, out=out, langs=langs, node_cwd=node_cwd)


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
    node_cwd: Path | None = typer.Option(
        None,
        help="Directory whose node_modules contains 'typescript' -- required when --src "
        "contains .js/.jsx/.ts/.tsx files (e.g. the frontend project root)",
    ),
) -> None:
    """Run only xgettext extraction."""
    run_xgettext_cmd(src=src, out=out, langs=langs, node_cwd=node_cwd)


@app.command("jinja")
def jinja_cmd(
    src: Path = typer.Option(Path("src"), help="Directory to scan for *.j2 templates"),
    out: Path = typer.Option(Path("templates.pot"), help="Output .pot file"),
) -> None:
    """Extract translatable strings from Jinja2 templates via Babel."""
    if not src.is_dir():
        console.print(f"[error] source directory not found: {src}")
        raise typer.Exit(code=1)
    if not BabelJinjaExtractor().run(src, out):
        raise typer.Exit(code=1)
    console.print(f"[done] jinja -> {out}")


@app.command("json")
def json_cmd(
    src: Path = typer.Option(Path("src"), help="Directory to scan for JSON resource files"),
    out: Path = typer.Option(Path("json.pot"), help="Output .pot file"),
    keys: str = typer.Option(
        ...,
        help="Comma-separated JSON keys whose string values are translatable (e.g. name,description,title,text)",
    ),
    pattern: str = typer.Option("*.json", help="Glob pattern (relative to --src) selecting JSON files"),
) -> None:
    """Extract translatable string values from JSON files by key (e.g. guided tours)."""
    if not src.is_dir():
        console.print(f"[error] source directory not found: {src}")
        raise typer.Exit(code=1)

    key_set = {k.strip() for k in keys.split(",") if k.strip()}
    if not key_set:
        console.print("[error] --keys must contain at least one non-empty key")
        raise typer.Exit(code=1)

    if not JsonKeysExtractor().run(src, out, key_set, pattern):
        raise typer.Exit(code=1)
    console.print(f"[done] json -> {out}")


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
    node_cwd: Path | None = typer.Option(
        None,
        help="Directory whose node_modules contains 'typescript' -- required when --src "
        "contains .js/.jsx/.ts/.tsx files (e.g. the frontend project root)",
    ),
) -> None:
    """Run xgettext then enrich."""
    run_xgettext_cmd(src=src, out=out, langs=langs, node_cwd=node_cwd)
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
