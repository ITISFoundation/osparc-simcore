#!/usr/bin/env -S uv run --no-cache --script
# /// script
# requires-python = ">=3.11"
# ///
# ruff: noqa: ERA001
#
# Hook: block-secrets-access
# Purpose: Deny agent read/write access to .env files, secrets files, and *.local files.
# Event:   preToolUse
#
# Works with the Local payload (tool_name/tool_input), the Copilot camelCase payload
# (toolName/toolArgs, where toolArgs may be a JSON string), and the PascalCase alias
# that reports Claude tool names (Read/Write/Edit/Bash/Grep). Output is one JSON
# object on stdout carrying both contracts: top-level permissionDecision for the
# Copilot harness plus a nested hookSpecificOutput copy for the legacy Local harness.
# Exit 0 for allow and for deny; exit 2 would surface as a blocking error in Local
# instead of the structured reason. No third-party dependencies, so the shebang runs
# it with the interpreter only and --no-cache avoids writing to a cache directory the
# hook sandbox may not expose.

from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterator
from typing import Any, Final

# ---------------------------------------------------------------------------
# Secrets path pattern
# Matches:
#   .env  .env.local  .env.production  etc.
#   .secret  .secrets
#   secrets.json / secrets.yaml / secrets.yml
#   credentials / credentials.json
#   vault.json
#   *.pem  *.key  *.p12  *.pfx  *.keystore  *.jks
#   id_rsa  id_ed25519  id_dsa  id_ecdsa  (SSH private keys)
#   *.local  (local overrides, e.g. secrets/local.yml, Makefile.local)
# ---------------------------------------------------------------------------
SECRETS_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    (^|[/])secrets([/]|$)
    | (^|[/])
      ( \.env(\.[^/]*)?
      | \.secret[s]?
      | secrets\.(json|ya?ml)
      | credentials(\.json)?
      | vault\.json
      | id_(rsa|ed25519|dsa|ecdsa)
      ) $
    | \.pem$
    | \.key$
    | \.p12$
    | \.pfx$
    | \.keystore$
    | \.jks$
    | \.local$
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Terminal commands that read or write secrets files, reference secrets/ at all,
# or pull them from git history.
CMD_PATTERNS: Final[tuple[str, ...]] = (
    r"(cat|less|more|head|tail|bat|nano|vi|vim|code)\s+.*\.env(\s|$|\.)",
    r"\s*>+\s*.*\.env(\s|$|\.)",
    r"(cat|less|more|head|tail|bat)\s+.*(\.pem|\.key|\.local|id_rsa|id_ed25519|secrets\.(json|ya?ml)|credentials)",
    r"\s*>+\s*.*(\.pem|\.key|\.local|id_rsa|\.env)",
    r"(^|[\s/])secrets([\s/]|$)",
    r"git\s+(show|log|diff|blame|cat-file)\b.*(\.env|secrets/|\.pem|\.key|id_rsa|id_ed25519|\.local)",
)
CMD_RES: Final[tuple[re.Pattern[str], ...]] = tuple(re.compile(p, re.IGNORECASE) for p in CMD_PATTERNS)

# Tool names per category, covering Local ids, Copilot runtime ids, and the Claude
# names reported under the PascalCase PreToolUse alias.
FILE_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "read_file",
        "create_file",
        "write_file",
        "edit_file",
        "replace_string_in_file",
        "multi_replace_string_in_file",
        "edit_notebook_file",
        "view",
        "create",
        "edit",
        "str_replace_editor",
        "apply_patch",
        "Read",
        "Write",
        "Edit",
    }
)
SEARCH_TOOLS: Final[frozenset[str]] = frozenset({"grep_search", "glob_search", "grep", "glob", "Grep", "Glob"})
SHELL_TOOLS: Final[frozenset[str]] = frozenset({"run_in_terminal", "bash", "powershell", "Bash"})

# Argument keys that carry a path or a search scope. Free-text keys such as "query"
# are deliberately absent: a prompt mentioning a token is not an access attempt.
PATH_KEYS: Final[tuple[str, ...]] = ("filePath", "path", "file_path", "file", "absolute_path", "notebook_path")
SEARCH_FILTER_KEYS: Final[tuple[str, ...]] = ("includePattern", "glob", "include", "path")

POLICY_NOTE: Final[str] = (
    " Do NOT retry via another tool, path, encoding, or git history."
    " If a credential is genuinely required, state your goal, why it is needed,"
    " the exact source, and alternatives considered, then ask the user."
)


class _DeniedError(Exception):
    """Raised internally when a tool call must be denied."""


def deny(reason: str) -> None:
    raise _DeniedError(reason)


def is_secrets_path(path: str) -> bool:
    return bool(path) and SECRETS_RE.search(path) is not None


def _iter_paths(tool_input: dict[str, Any]) -> Iterator[str]:
    for key in PATH_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            yield value
    for group_key in ("replacements", "edits"):
        items = tool_input.get(group_key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    yield from _iter_paths(item)


def normalize_event(event: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    tool_name = str(event.get("tool_name") or event.get("toolName") or "")
    raw_args = event.get("tool_input", event.get("toolArgs", event.get("toolInput")))
    if isinstance(raw_args, str):
        try:
            raw_args = json.loads(raw_args)
        except json.JSONDecodeError:
            # An unparsable string can only be a raw command line; treat it as one so
            # shell checks still see it.
            raw_args = {"command": raw_args}
    tool_input = raw_args if isinstance(raw_args, dict) else {}
    return tool_name, tool_input


def check(tool_name: str, tool_input: dict[str, Any]) -> None:
    if tool_name in FILE_TOOLS:
        for path in _iter_paths(tool_input):
            if is_secrets_path(path):
                deny(f"Access to secrets/.env files is blocked by policy: {path}")
    elif tool_name in SEARCH_TOOLS:
        for key in SEARCH_FILTER_KEYS:
            value = tool_input.get(key)
            if isinstance(value, str) and is_secrets_path(value):
                deny(f"Searching inside secrets/.env files is blocked by policy: {value}")
    elif tool_name in SHELL_TOOLS:
        command = str(tool_input.get("command") or tool_input.get("cmd") or "")
        if any(rx.search(command) for rx in CMD_RES):
            deny("Terminal command accessing secrets/.env files is blocked by policy")


def _emit(obj: dict[str, Any]) -> None:
    print(json.dumps(obj))  # noqa: T201


def _emit_deny(reason: str) -> None:
    full_reason = reason + POLICY_NOTE
    _emit(
        {
            "permissionDecision": "deny",
            "permissionDecisionReason": full_reason,
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": full_reason,
            },
        }
    )


def main() -> None:
    try:
        raw = sys.stdin.read()
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            event = {}
        if not isinstance(event, dict):
            event = {}
        tool_name, tool_input = normalize_event(event)
        check(tool_name, tool_input)
    except _DeniedError as exc:
        _emit_deny(str(exc))
        return
    except Exception:  # pylint: disable=broad-exception-caught
        # Fail closed: a broken guard must not silently let a tool call through.
        _emit_deny(
            "block-secrets-access hook failed to evaluate this tool call, so it is"
            " denied. Tell the user to check the hook"
            " (.github/hooks/scripts/block-secrets-access.py) or set"
            ' "disableAllHooks": true in .github/hooks/block-secrets-access.json.'
        )
        return
    _emit({})


if __name__ == "__main__":
    main()
