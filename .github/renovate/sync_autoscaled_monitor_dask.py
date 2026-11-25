#!/usr/bin/env -S uv run --script --no-project
# /// script
# requires-python = ">=3.14"
# dependencies = []
# ///
# ruff: noqa: T201  # the report of a Renovate post-upgrade task is its stdout/stderr log
"""Renovate post-upgrade task (postUpgradeTasks in .renovaterc.jsonc), run right after
resync_lockfiles.py and before Renovate commits.

dask is unpinned in every requirements/*.in, so the version the cluster runs lives in
services/dask-sidecar/requirements/_dask-distributed.txt. autoscaled-monitor is a dask
client and pins that same version in its pyproject.toml and uv.lock, which the pep621
manager reads while the lockfile belongs to pip-compile: one run moves one of the two.
This task pins the CLI to the sidecar's version with the same `uv add` the CLI's
`make sync-dask-version` runs.

Only a branch whose pins file names dask triggers it, so an unrelated branch never
carries a CLI version change. A CLI pin that drifts any other way is caught by
tests/environment-setup/test_used_dask.py, not fixed here.

A failed sync reports in renovate-resync-report.md and exits 0: a non-zero exit makes
Renovate drop the branch, so the dask update would not open a pull request at all.

Usage: sync_autoscaled_monitor_dask.py [PINS_FILE]
  PINS_FILE: one "<package>==<version>" per line, defaults to
  $RENOVATE_POST_UPGRADE_COMMAND_DATA_FILE, the data file Renovate renders from
  postUpgradeTasks.dataFileTemplate. To try it by hand, run it from a scratch git
  worktree with a file holding "dask==<version>".
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Final

if TYPE_CHECKING:
    # documentation metadata only, and `annotated-types` is not a dependency of this
    # script (see the metadata block above): `from __future__ import annotations` keeps
    # these annotations from ever being evaluated at runtime
    from annotated_types import doc

SIDECAR_LOCKFILE: Final[
    Annotated[
        str,
        doc("The lockfile the dask-sidecar image installs, i.e. what the cluster runs"),
    ]
] = "services/dask-sidecar/requirements/_dask-distributed.txt"

CLI_DIR: Final[
    Annotated[
        str,
        doc("The dask client, pinned in its pyproject.toml and uv.lock"),
    ]
] = "scripts/maintenance/autoscaled-monitor"

REPORT_FILE: Final[
    Annotated[
        str,
        doc("The post-upgrade report Renovate commits to its PR (fileFilters); appended to, never rewritten"),
    ]
] = "renovate-resync-report.md"

SIDECAR_DASK_PIN: Final[
    Annotated[
        re.Pattern[str],
        doc("The dask pin of a pip-compile lockfile, `dask==2026.8.0` at the start of a line"),
    ]
] = re.compile(r"^dask==(?P<version>[^\s#]+)", re.MULTILINE)

PIN: Final[
    Annotated[
        re.Pattern[str],
        doc("A `<package>==<version>` pin of the pins file, extras optional, as the dataFileTemplate renders them"),
    ]
] = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?)==([A-Za-z0-9._+!-]+)\s*$")


def git(*args: str) -> str:
    output = subprocess.run(["git", *args], check=True, capture_output=True, text=True)  # noqa: S603, S607
    return output.stdout


def _base_name(name: str) -> str:
    """`dask[distributed]` -> `dask`, the name uv and PyPI normalize to"""
    return name.split("[", 1)[0].strip().lower().replace("_", "-")


def parse_pins(text: str) -> dict[str, str]:
    """Pins in the file, by normalized package name; a repeated name keeps its first pin"""
    pins: dict[str, str] = {}
    for line in text.splitlines():
        if match := PIN.match(line.strip()):
            name, version = _base_name(match[1]), match[2]
            if name not in pins:
                pins[name] = version
    return pins


def sidecar_dask_version() -> str | None:
    path = Path(SIDECAR_LOCKFILE)
    if not path.is_file():
        return None
    if match := SIDECAR_DASK_PIN.search(path.read_text()):
        return match["version"]
    return None


def cli_dask_pinned_version() -> str | None:
    """The dask version the CLI pins, or None when it does not pin one (then uv is free
    to pick, and there is nothing to keep in step)"""
    pyproject = tomllib.loads((Path(CLI_DIR) / "pyproject.toml").read_text())
    for dependency in pyproject["project"]["dependencies"]:
        if _base_name(dependency.split("<")[0].split(">")[0].split("=")[0]) == "dask" and "==" in dependency:
            return dependency.rsplit("==", 1)[1].strip().strip("'\"")
    return None


def sync_cli_to(version: str) -> subprocess.CompletedProcess[str]:
    """Pins the CLI's dask to `version` and rewrites uv.lock, like `make sync-dask-version`.

    `--no-sync` keeps uv from creating a virtual environment; the lockfile is all
    Renovate has to commit."""
    command = ["uv", "add", "--no-sync", f"dask[distributed]=={version}"]
    try:
        return subprocess.run(  # noqa: S603
            command,
            cwd=CLI_DIR,
            check=False,
            stdout=subprocess.PIPE,
            # uv writes its errors to stderr
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as error:
        # uv comes from postUpgradeTasks.installTools; a runner without it must report
        # the missed sync instead of failing the branch with a traceback
        return subprocess.CompletedProcess(command, returncode=127, stdout=f"{error}", stderr="")


def report_failure(version: str, output: str) -> None:
    section = (
        f"## {CLI_DIR}\n\n"
        f"Could not pin dask to the dask-sidecar version {version} (`uv add --no-sync`).\n"
        "The CLI stays on its own pin, so `tests/environment-setup/test_used_dask.py` fails on this branch."
        " Run `make sync-dask-version` in the directory and push it here.\n\n"
        f"```\n{output.strip()[-2000:]}\n```\n"
    )
    path = Path(REPORT_FILE)
    previous = path.read_text().rstrip() if path.is_file() else ""
    path.write_text(f"{previous}\n\n{section}" if previous else f"# Post-upgrade tasks\n\n{section}")
    print(f"--- wrote {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Keep the autoscaled-monitor CLI on the dask version the dask-sidecar lockfile pins"
    )
    parser.add_argument(
        "pins_file",
        nargs="?",
        metavar="PINS_FILE",
        help="file with one '<package>==<version>' per line (defaults to $RENOVATE_POST_UPGRADE_COMMAND_DATA_FILE)",
    )
    args = parser.parse_args()

    pins_file = args.pins_file or os.environ.get("RENOVATE_POST_UPGRADE_COMMAND_DATA_FILE", "")
    if not pins_file:
        parser.print_help()
        return 2
    if not Path(pins_file).is_file():
        print(f"error: pins file not found: '{pins_file}'", file=sys.stderr)
        return 2

    os.chdir(Path(git("rev-parse", "--show-toplevel").strip()))

    pins = parse_pins(Path(pins_file).read_text())
    if "dask" not in pins:
        print("No dask update on this branch, leaving the autoscaled-monitor CLI alone")
        return 0

    version = sidecar_dask_version()
    if version is None:
        print(f"warning: no dask pin in {SIDECAR_LOCKFILE}, cannot tell what the cluster runs")
        return 0

    current = cli_dask_pinned_version()
    if current == version:
        print(f"{CLI_DIR} already pins dask {version}, as {SIDECAR_LOCKFILE} does")
        return 0

    print(f"Pinning {CLI_DIR} to dask {version} (from {SIDECAR_LOCKFILE}), it was on {current}")
    result = sync_cli_to(version)
    print(result.stdout.rstrip())
    if result.returncode != 0:
        report_failure(version, result.stdout)
    elif cli_dask_pinned_version() != version:
        report_failure(version, f"uv add exited 0 but {CLI_DIR} pins dask {cli_dask_pinned_version()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
