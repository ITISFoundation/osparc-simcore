"""Regression tests for the block-secrets-access preToolUse hook.

The hook must work for the legacy Local payload (tool_name/tool_input), the Copilot
camelCase payload (toolName/toolArgs, with toolArgs possibly a JSON string), and the
PascalCase alias that reports Claude tool names. Subprocess tests run the script via
sys.executable; one smoke test exercises the real shebang, which must work with the
plain interpreter environment a hook process sees.

Run from the repo root:
    pytest .github/hooks/scripts/test_block_secrets_access.py -v
"""

from __future__ import annotations

import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Final

import pytest

SCRIPT: Final[Path] = Path(__file__).parent / "block-secrets-access.py"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("block_secrets_access", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE: Final[Any] = _load_module()


def _run_hook(event: dict[str, Any] | str) -> subprocess.CompletedProcess[str]:
    payload = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run(  # noqa: S603
        # fixed in-repo fixture payloads piped to the repo's own hook script
        [sys.executable, str(SCRIPT)],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _run_hook_json(event: dict[str, Any]) -> dict[str, Any]:
    proc = _run_hook(event)
    assert proc.returncode == 0, f"hook must exit 0, got {proc.returncode}: {proc.stderr}"
    # The harness concatenates stdout and parses it with a single JSON.parse, so the
    # whole stdout must be exactly one object. Two concatenated objects are ignored by
    # the harness, which would silently bypass the policy.
    out = json.loads(proc.stdout)
    assert isinstance(out, dict)
    return out


def _assert_denied(out: dict[str, Any]) -> None:
    assert out["permissionDecision"] == "deny"
    assert out["permissionDecisionReason"].strip()
    nested = out["hookSpecificOutput"]
    assert nested["hookEventName"] == "PreToolUse"
    assert nested["permissionDecision"] == "deny"
    assert nested["permissionDecisionReason"] == out["permissionDecisionReason"]


# ---------------------------------------------------------------------------
# Path pattern, unit level
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "/abs/path/.env",
        ".env.local",
        "services/.env.production",
        "secrets/db.json",
        "secrets",
        "deploy/secrets/local.yml",
        "srv/tls.pem",
        "keys/sign.key",
        "id_ed25519",
        "Makefile.local",
        "cfg/vault.json",
        "credentials.json",
    ],
)
def test_secrets_paths_are_detected(path: str) -> None:
    assert MODULE.is_secrets_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "README.md",
        "src/main.py",
        ".environment",
        "package.json",
        "secretsstore/notes.md",
        "monkey.pem2",
    ],
)
def test_normal_paths_are_allowed(path: str) -> None:
    assert not MODULE.is_secrets_path(path)


@pytest.mark.parametrize(
    "command",
    [
        "cat .env",
        "echo secret >> services/web/.env",
        "head -5 deploy/secrets/db.yaml",
        "git show HEAD~2:secrets/token.pem",
        "git log -p -- config/aws.local",
        "ls secrets/",
    ],
)
def test_secret_commands_are_detected(command: str) -> None:
    assert any(rx.search(command) for rx in MODULE.CMD_RES)


@pytest.mark.parametrize(
    "command",
    [
        "ls",
        "grep -r token src/",
        "git log --oneline -5",
        "pytest tests/",
    ],
)
def test_normal_commands_pass(command: str) -> None:
    assert not any(rx.search(command) for rx in MODULE.CMD_RES)


# ---------------------------------------------------------------------------
# End-to-end contract per harness payload shape
# ---------------------------------------------------------------------------


def test_local_payload_denies_dotenv_read() -> None:
    out = _run_hook_json(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "read_file",
            "tool_input": {"filePath": "/repo/.env"},
        }
    )
    _assert_denied(out)


def test_copilot_camelcase_json_string_args_denied() -> None:
    out = _run_hook_json(
        {
            "toolName": "view",
            "toolArgs": json.dumps({"path": "deploy/secrets/db.json"}),
        }
    )
    _assert_denied(out)


def test_copilot_camelcase_dict_args_denied() -> None:
    out = _run_hook_json({"toolName": "bash", "toolArgs": {"command": "cat .env"}})
    _assert_denied(out)


def test_pascalcase_claude_names_git_history_denied() -> None:
    out = _run_hook_json(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git show HEAD:secrets/token.pem"},
        }
    )
    _assert_denied(out)


def test_multi_replace_nested_paths_denied() -> None:
    out = _run_hook_json(
        {
            "tool_name": "multi_replace_string_in_file",
            "tool_input": {"replacements": [{"filePath": "a/secrets/x.json", "oldString": "a", "newString": "b"}]},
        }
    )
    _assert_denied(out)


def test_search_scope_on_secrets_denied() -> None:
    out = _run_hook_json({"toolName": "grep", "toolArgs": {"includePattern": "**/.env"}})
    _assert_denied(out)


def test_search_free_text_is_not_scanned() -> None:
    out = _run_hook_json({"toolName": "grep", "toolArgs": {"query": "token", "includePattern": "**/*.py"}})
    assert out == {}


@pytest.mark.parametrize(
    "event",
    [
        {"tool_name": "read_file", "tool_input": {"filePath": "README.md"}},
        {"toolName": "view", "toolArgs": {"path": "src/main.py"}},
        {"tool_name": "run_in_terminal", "tool_input": {"command": "ls -la"}},
        {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": "docs/README.md"}},
        {},
    ],
    ids=["local-allow", "copilot-allow", "shell-allow", "claude-allow", "empty-event"],
)
def test_allow_cases_emit_no_decision(event: dict[str, Any]) -> None:
    assert _run_hook_json(event) == {}


def test_malformed_stdin_emits_single_allow_object() -> None:
    proc = _run_hook("not-json")
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {}


def test_deny_is_single_json_document() -> None:
    proc = _run_hook({"tool_name": "read_file", "tool_input": {"filePath": "secrets/x.yaml"}})
    assert proc.returncode == 0
    json.loads(proc.stdout)  # raises on two concatenated objects


# ---------------------------------------------------------------------------
# Static invariants of the hook itself
# ---------------------------------------------------------------------------


def test_script_is_executable() -> None:
    mode = SCRIPT.stat().st_mode
    assert mode & stat.S_IXUSR, "shebang execution requires the owner exec bit"


def test_script_uses_plain_python_shebang() -> None:
    first_line = SCRIPT.read_text().splitlines()[0]
    assert first_line == "#!/usr/bin/env python3"


def test_hook_json_targets_copilot_contract() -> None:
    config = json.loads((SCRIPT.parent.parent / "block-secrets-access.json").read_text())
    assert config["version"] == 1
    (entry,) = config["hooks"]["preToolUse"]
    # The hook is stdlib-only and must not depend on uv: the Copilot harness
    # process may lack uv on PATH, and a failing preToolUse hook denies everything.
    repo_root = SCRIPT.parent.parent.parent.parent
    for field in ("command", "bash"):
        assert "uv" not in entry[field]
        assert entry[field] == f"python3 {SCRIPT.relative_to(repo_root)}"
    assert "timeoutSec" in entry
    assert "timeout" not in entry


def test_script_runs_through_its_shebang() -> None:
    proc = subprocess.run(  # noqa: S603
        # fixed in-repo fixture payload piped to the repo's own hook script
        [str(SCRIPT)],
        input=json.dumps({"tool_name": "read_file", "tool_input": {"filePath": ".env"}}),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["permissionDecision"] == "deny"
