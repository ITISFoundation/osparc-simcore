# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "polib>=1.2.0",
#   "pytest>=8.0.0",
#   "rich>=13.0.0",
#   "typer>=0.12.0",
# ]
# ///
"""
tools/tests/test_i18n_extractor_ts_ast_qooxdoo.py

Regression tests for `TypeScriptAstExtractor` (i18n_extractor.py): qooxdoo's
translation calls are exclusively property-access forms -- `this.tr("...")` and
`qx.locale.Manager.tr("...")` -- never a bare `tr("...")`/`t("...")` identifier
call. These tests pin that both forms are extracted, alongside the bare form
(non-qooxdoo callers), while unrelated `.someMethod("...")` calls are not.

Requires Node.js + the local `typescript` package (installed via
`scripts/i18n/tools/package.json` / `make -C scripts/i18n frontend-tools-install`);
skipped automatically when either is unavailable.

Run:
    uv run --with pytest pytest scripts/i18n/tools/tests/test_i18n_extractor_ts_ast_qooxdoo.py
"""

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent.parent
NODE_CWD = TOOLS_DIR  # scripts/i18n/tools/node_modules/typescript is installed here


def _load_i18n_extractor() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("i18n_extractor", TOOLS_DIR / "i18n_extractor.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


i18n_extractor = _load_i18n_extractor()


def _node_available() -> bool:
    result = subprocess.run(
        ["which", "node"],  # noqa: S607
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _typescript_installed() -> bool:
    return (NODE_CWD / "node_modules" / "typescript").exists()


requires_node_ts = pytest.mark.skipif(
    not _node_available() or not _typescript_installed(),
    reason=(
        "node + local typescript (scripts/i18n/tools/node_modules) required, "
        "run `make -C scripts/i18n frontend-tools-install`"
    ),
)


def _extract_msgids(src_dir: Path, out_pot: Path) -> set[str]:
    js_files = sorted(src_dir.rglob("*.js"))
    ok = i18n_extractor.TypeScriptAstExtractor().run(js_files, out_pot, src_dir, NODE_CWD, merge_into_existing=False)
    assert ok
    po = i18n_extractor.polib.pofile(str(out_pot))
    return {entry.msgid for entry in po}


@requires_node_ts
def test_ts_ast_extractor_matches_this_tr(tmp_path: Path) -> None:
    src_dir = tmp_path / "class"
    src_dir.mkdir()
    (src_dir / "Widget.js").write_text(
        'qx.Class.define("osparc.Widget", {\n'
        "  members: {\n"
        "    __build: function() {\n"
        '      this.setLabel(this.tr("Help & Support"));\n'
        "    }\n"
        "  }\n"
        "});\n"
    )

    msgids = _extract_msgids(src_dir, tmp_path / "out.pot")

    assert "Help & Support" in msgids


@requires_node_ts
def test_ts_ast_extractor_matches_qx_locale_manager_tr(tmp_path: Path) -> None:
    src_dir = tmp_path / "class"
    src_dir.mkdir()
    (src_dir / "StatusUI.js").write_text(
        'qx.Class.define("osparc.StatusUI", {\n'
        "  statics: {\n"
        "    getLabel: function(state) {\n"
        '      return qx.locale.Manager.tr("Running");\n'
        "    }\n"
        "  }\n"
        "});\n"
    )

    msgids = _extract_msgids(src_dir, tmp_path / "out.pot")

    assert "Running" in msgids


@requires_node_ts
def test_ts_ast_extractor_matches_bare_tr(tmp_path: Path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "i18n.js").write_text('const label = tr("Standalone");\n')

    msgids = _extract_msgids(src_dir, tmp_path / "out.pot")

    assert "Standalone" in msgids


@requires_node_ts
def test_ts_ast_extractor_does_not_match_unrelated_property_call(tmp_path: Path) -> None:
    src_dir = tmp_path / "class"
    src_dir.mkdir()
    (src_dir / "Widget.js").write_text('this.trim("Should Not Extract");\n')

    msgids = _extract_msgids(src_dir, tmp_path / "out.pot")

    assert "Should Not Extract" not in msgids


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
