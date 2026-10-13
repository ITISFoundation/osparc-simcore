#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
# ruff: noqa: ERA001
#
# Hook: block-secrets-access
# Purpose: Deny agent read/write access to .env files, secrets files, and *.local files.
# Event:   PreToolUse
# Exit 2 = blocking error (with a deny decision on stdout); exit 0 = allow.
#
# Self-contained: the PEP 723 block above declares no third-party dependencies, so
# `uv run --script` executes it with the interpreter only -- nothing is installed.

from __future__ import annotations

import json
import re
import sys
from typing import Any

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
SECRETS_RE = re.compile(
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

# Terminal commands that read or write secrets files, or reference secrets/ at all.
CMD_PATTERNS = (
    r"(cat|less|more|head|tail|bat|nano|vi|vim|code)\s+.*\.env(\s|$|\.)",
    r"\s*>+\s*.*\.env(\s|$|\.)",
    r"(cat|less|more|head|tail|bat)\s+.*(\.pem|\.key|\.local|id_rsa|id_ed25519|secrets\.(json|ya?ml)|credentials)",
    r"\s*>+\s*.*(\.pem|\.key|\.local|id_rsa|\.env)",
    r"(^|[\s/])secrets([\s/]|$)",
)
CMD_RES = tuple(re.compile(p, re.IGNORECASE) for p in CMD_PATTERNS)

FILE_TOOLS = frozenset({"read_file", "create_file", "replace_string_in_file", "write_file", "edit_file"})


POLICY_NOTE = (
    " Do NOT retry via another tool, path, encoding, or git history."
    " Follow the credentials contract (.github/prompts/"
    "credentials.instructions.md): state your goal, why the credential is needed,"
    " the exact source, and alternatives considered, then ask the user."
)


def deny(reason: str) -> None:
    """Emit a PreToolUse deny decision and exit with a blocking status."""
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason + POLICY_NOTE,
        }
    }
    print(json.dumps(payload))  # noqa: T201
    sys.exit(2)


def is_secrets_path(path: str) -> bool:
    return bool(path) and SECRETS_RE.search(path) is not None


def _single_path(tool_input: dict[str, Any]) -> str:
    return str(tool_input.get("filePath", tool_input.get("path", tool_input.get("file", ""))))


def _multi_paths(tool_input: dict[str, Any]) -> list[str]:
    return [
        str(r.get("filePath", ""))
        for r in tool_input.get("replacements", [])
        if isinstance(r, dict) and r.get("filePath")
    ]


def check(tool_name: str, tool_input: dict[str, Any]) -> None:
    if tool_name in FILE_TOOLS or tool_name == "multi_replace_string_in_file":
        paths = _multi_paths(tool_input) if tool_name == "multi_replace_string_in_file" else [_single_path(tool_input)]
        for path in paths:
            if is_secrets_path(path):
                deny(f"Access to secrets/.env files is blocked by policy: {path}")
    elif tool_name == "grep_search":
        include = str(tool_input.get("includePattern", ""))
        if is_secrets_path(include):
            deny(f"Searching inside secrets/.env files is blocked by policy: {include}")
    elif tool_name == "run_in_terminal":
        command = str(tool_input.get("command", ""))
        if any(rx.search(command) for rx in CMD_RES):
            deny("Terminal command accessing secrets/.env files is blocked by policy")


def main() -> None:
    try:
        event = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        event = {}
    if not isinstance(event, dict):
        event = {}
    tool_input = event.get("toolInput") or {}
    check(
        str(event.get("toolName", "")),
        tool_input if isinstance(tool_input, dict) else {},
    )
    print(json.dumps({"continue": True}))  # noqa: T201


if __name__ == "__main__":
    main()
