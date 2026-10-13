#!/bin/env python
# ruff: noqa: T201, PLR2004
"""Checks that the virtual environment of *this* checkout is the active one.

Every git worktree keeps its own ``.venv``, so merely having *a* virtual environment
active is not enough: one inherited from another checkout silently installs and tests
the wrong sources.
"""

import pathlib
import sys

_usage = f"usage: {sys.argv[0]} <expected-venv-dir>"


def main() -> int:
    if len(sys.argv) != 2:
        print(_usage, file=sys.stderr)
        return 1

    expected = pathlib.Path(sys.argv[1]).resolve()
    active = pathlib.Path(sys.prefix).resolve()

    if sys.base_prefix == sys.prefix:
        print(
            "no virtual environment activated. Run: make devenv && source .venv/bin/activate",
            file=sys.stderr,
        )
        return 1

    if active != expected:
        print(
            f"wrong virtual environment activated: {active}. This checkout needs its own:"
            f" source {expected}/bin/activate (then make install-dev)",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
