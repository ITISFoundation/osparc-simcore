#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
# Agent hook (PostToolUse): run pre-commit on the file the agent just edited.
#
# The hook event arrives as JSON on stdin; findings are returned on stdout as
# additional context so the agent can fix them immediately. Exits 0 on any
# problem so a broken hook never blocks the agent.
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

try:
    event = json.load(sys.stdin)
    file_path = (event.get("tool_input") or {}).get("file_path", "")
except (json.JSONDecodeError, AttributeError):
    sys.exit(0)

if not file_path or not Path(file_path).is_file():
    sys.exit(0)

pre_commit = shutil.which("pre-commit")
if pre_commit is None:
    sys.exit(0)

try:
    # argv is fixed; file_path comes from the agent's own edit tool input
    result = subprocess.run(  # noqa: S603
        [pre_commit, "run", "--files", file_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=110,
        check=False,
    )
except (FileNotFoundError, subprocess.TimeoutExpired):
    sys.exit(0)

if result.returncode == 0:
    sys.exit(0)

output = (result.stdout + result.stderr)[:8000]
json.dump(
    {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"pre-commit found issues in {file_path}:\n{output}",
        }
    },
    sys.stdout,
)
