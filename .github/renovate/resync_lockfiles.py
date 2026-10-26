#!/usr/bin/env -S uv run --script --no-project
# /// script
# requires-python = ">=3.14"
# dependencies = [] # stdlib-only on purpose: this is the only command the Renovate
#                   # runner may execute, so it must never fetch anything to start
# ///
# ruff: noqa: T201  # the report of a Renovate post-upgrade task is its stdout/stderr log
"""Renovate post-upgrade task (postUpgradeTasks in .renovaterc.jsonc), run by the
self-hosted Renovate of .github/workflows/chore-renovate.yml before it commits.

Renovate's pip-compile manager recompiles each requirements/*.txt on its own and
never moves a pin in a parent layer (_base -> _test -> _tools, see
scripts/makefiles/requirements.mk), so an update can leave the lockfiles
inconsistent or even unresolvable. This re-runs `make reqs upgrade="<pkg==ver ...>"`
in every requirements directory the update touches or that pins one of the updated
packages at another version. Renovate's versions are passed as exact pins on purpose:
a bare `make reqs` upgrades everything and a bare package name lets uv pick the
latest release. Only packages that block the update are passed by name (see
resync_dir below).

Usage: resync_lockfiles.py [PINS_FILE]
  PINS_FILE: one "<package>==<version>" per line, defaults to
  $RENOVATE_POST_UPGRADE_COMMAND_DATA_FILE, the data file Renovate renders from
  postUpgradeTasks.dataFileTemplate. To try it by hand, run it with
  .github/renovate/resync_lockfiles.example.txt inside a scratch git worktree.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Final

# the pip-compile lockfiles, same set as pip-compile.managerFilePatterns in .renovaterc.jsonc
MANAGED: Final[re.Pattern[str]] = re.compile(
    r"^(?:.*/)?requirements/_[^/]+\.txt$"
    r"|^(?:api/tests|ci/helpers/requirements|tests/environment-setup/requirements)/requirements\.txt$"
)

# a "<package>==<version>" pin, extras included, as in `python-socketio[asyncio-client]==5.16.4`
PIN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?==[A-Za-z0-9._+!-]*[A-Za-z0-9]")
# a line starting with such a pin, as lockfiles and uv error messages write them
PIN_AT_LINE_START: Final[re.Pattern[str]] = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?)==([^ ;]+)")
MAKE_LOG: Final[re.Pattern[str]] = re.compile(r"^make(\[\d+\])?: ")

# rounds of letting uv's blamed packages move before giving up on a directory
MAX_UNBLOCK_ROUNDS: Final[int] = 5


def normalized(name: str) -> str:
    """PEP 503-normalized name, without extras (`uvicorn[standard]` -> `uvicorn`)"""
    return re.sub(r"[-_.]+", "-", re.sub(r"\[[^\]]*\]", "", name).lower())


def _version_key(version: str) -> list[tuple[int, str]]:
    # orders versions like GNU `sort -V`: runs of digits compare numerically (so
    # 3.14.10 > 3.14.9), other characters compare as text and rank below digits
    return [(int(part), "") if part.isdigit() else (0, part) for part in re.split(r"(\d+)", version) if part]


def parse_pins(text: str) -> list[str]:
    """The raw pins to propagate, one per normalized package name.

    Lines without a version (e.g. lock file maintenance) carry nothing to propagate.
    A Renovate branch can carry the same package at several versions, and uv cannot
    satisfy two exact pins of one package, so only the highest version of each
    (PEP 503-normalized) name is kept.
    """
    highest: dict[str, tuple[list[tuple[int, str]], str]] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip(" \r")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(\[[^\]]+\])?==[A-Za-z0-9._+!-]+", line):
            continue
        name, _, version = line.partition("==")
        name = normalized(name)
        key = _version_key(version)
        if name not in highest or key > highest[name][0]:
            highest[name] = (key, line)
    return [highest[name][1] for name in sorted(highest)]


def git(*args: str) -> str:
    output = subprocess.run(["git", *args], check=True, capture_output=True, text=True)  # noqa: S603, S607
    return output.stdout


def directories_to_resync(pins: list[str]) -> list[str]:
    """Directories Renovate modified, plus every directory pinning one of the updated
    packages at another version, so the version Renovate replaces cannot survive
    elsewhere in the monorepo. Names are compared PEP 503-normalized and without extras
    (`uvicorn[standard]==1.2` matches `uvicorn==1.2`)."""
    targets: dict[str, str] = {}
    for pin in pins:
        name, _, version = pin.partition("==")
        targets[normalized(name)] = version

    locks = [file for file in git("ls-files").splitlines() if MANAGED.match(file)]

    # Directories Renovate already modified (uncommitted at this point) ...
    changed = {
        str(Path(file).parent) for file in git("diff", "--name-only", "HEAD").splitlines() if MANAGED.match(file)
    }
    # ... plus the directories still pinning one of the updated packages elsewhere
    lagging: set[str] = set()
    for lock in locks:
        for line in Path(lock).read_text().splitlines():
            if match := PIN_AT_LINE_START.match(line):
                name, version = match.groups()
                if targets.get(normalized(name), version) != version:
                    lagging.add(str(Path(lock).parent))
                    break
    return sorted(changed | lagging)


class DirectorySnapshot:
    """Keeps the lockfiles as Renovate left them, to fall back to when a directory cannot
    be resolved (restoring from git would also drop Renovate's own changes)"""

    def __init__(self, backup_dir: Path) -> None:
        self._backup_dir = backup_dir

    def snapshot(self, directory: str) -> None:
        backup = self._backup_dir / directory
        backup.mkdir(parents=True, exist_ok=True)
        for lockfile in Path(directory).glob("*.txt"):
            shutil.copy2(lockfile, backup / lockfile.name)

    def restore(self, directory: str) -> None:
        for lockfile in (self._backup_dir / directory).glob("*.txt"):
            shutil.copy2(lockfile, Path(directory) / lockfile.name)


def regenerate(directory: str, upgrade: str) -> subprocess.CompletedProcess[str]:
    """Regenerates one directory with the given upgrade list. The inputs are touched first
    so the rules run even though the lockfiles may look newer than them (the Makefiles'
    own `touch` target is missing e.g. in api/tests)."""
    for template in Path(directory).glob("*.in"):
        os.utime(template, None)
    return subprocess.run(  # noqa: S603
        ["make", "-C", directory, "reqs", f"upgrade={upgrade}"],  # noqa: S607
        check=False,
        stdout=subprocess.PIPE,
        # uv writes its errors to stderr; keep them interleaved with the layer output
        stderr=subprocess.STDOUT,
        text=True,
    )


def _error_block(output: str) -> str:
    """uv's own error only: before it, the output holds the full lockfiles of the layers
    that did resolve, and every pin in there would otherwise look blamed."""
    lines: list[str] = []
    in_error = False
    for line in output.splitlines():
        if line.startswith("error:"):
            in_error = True
        elif MAKE_LOG.match(line):
            in_error = False
        if in_error:
            lines.append(line)
    return "\n".join(lines)


def blamed_packages(output: str, directory: str, upgrade: str) -> set[str]:
    """The (PEP 503-normalized) names of the packages uv's error message blames at
    exactly the version the directory's lockfiles pin, e.g. "packaging" for
    "virtualenv==21.14.10 depends on packaging>=26.3 and packaging==24.1", leaving out
    those the upgrade list already lets move."""
    # compare normalized, so an error that writes `PyYAML` still matches the `pyyaml` pin
    blamed = set[str]()
    for pin in PIN.findall(_error_block(output)):
        name, _, version = pin.partition("==")
        blamed.add(f"{normalized(name)}=={version}")

    free = {normalized(entry.partition("==")[0]) for entry in upgrade.split()}
    names: set[str] = set()
    for lockfile in Path(directory).glob("*.txt"):
        for line in lockfile.read_text().splitlines():
            if match := PIN_AT_LINE_START.match(line):
                name, version = match.groups()
                if f"{normalized(name)}=={version}" in blamed and normalized(name) not in free:
                    names.add(normalized(name))
    return names


def resync_dir(directory: str, pins: str, snapshot: DirectorySnapshot) -> tuple[bool, str]:
    """Regenerates one directory.

    uv treats a lockfile as a hard constraint, so a pin in another layer can leave
    Renovate's pins without a solution, e.g. a new virtualenv in _tools.txt needs
    packaging>=26.3 while _base.txt pins packaging==24.1. uv names such a pin in its
    error, so up to MAX_UNBLOCK_ROUNDS rounds let the blamed packages move as well.
    Only packages that block the update move.

    Returns (solved, the extra pins that had to move).
    """
    upgrade = pins
    for _ in range(MAX_UNBLOCK_ROUNDS + 1):
        process = regenerate(directory, upgrade)
        print(process.stdout, end="")
        if process.returncode == 0:
            return True, upgrade.removeprefix(pins).strip()
        snapshot.restore(directory)

        names = blamed_packages(process.stdout, directory, upgrade)
        if not names:
            return False, ""

        print(
            f'warning: {directory}: {" ".join(sorted(names))} blocks "{pins}", letting it move too',
            file=sys.stderr,
        )
        upgrade = f"{upgrade} {' '.join(sorted(names))}"

    return False, ""


def report(unblocked: list[str], failed: list[str]) -> int:
    if unblocked:
        print(f"warning: these packages had to move too: {' '.join(unblocked)}", file=sys.stderr)
    if failed:
        print(
            f"error: could not regenerate the lockfiles in: {' '.join(failed)} (left as Renovate produced them)",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Propagate Renovate's lockfile updates across the monorepo")
    parser.add_argument(
        "pins_file",
        nargs="?",
        metavar="PINS_FILE",
        help="file with one '<package>==<version>' per line, e.g."
        " .github/renovate/resync_lockfiles.example.txt (defaults to"
        " $RENOVATE_POST_UPGRADE_COMMAND_DATA_FILE)",
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
    if not pins:
        print("No version pins to propagate")
        return 0
    print(f"Propagating pins: {' '.join(pins)}")

    directories = directories_to_resync(pins)
    if not directories:
        print("No lockfile needs regenerating")
        return 0
    print("Regenerating lockfiles in:")
    for directory in directories:
        print(f"  - {directory}")

    backup_dir = Path(tempfile.mkdtemp())
    try:
        snapshot = DirectorySnapshot(backup_dir)

        upgrade = " ".join(pins)
        unblocked: list[str] = []
        failed: list[str] = []
        for directory in directories:
            print(f"--- {directory}")
            snapshot.snapshot(directory)
            solved, moved = resync_dir(directory, upgrade, snapshot)
            if solved:
                if moved:
                    unblocked.append(f"{directory} ({moved})")
            else:
                snapshot.restore(directory)
                failed.append(directory)

        return report(unblocked, failed)
    finally:
        shutil.rmtree(backup_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
