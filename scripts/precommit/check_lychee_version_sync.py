#!/usr/bin/env python3
"""Keep the lychee hook's `rev` and its LYCHEE_VERSION argument in sync.

The lychee script hook uses the LYCHEE_VERSION argument to pick its binary and
never looks at `rev`. `pre-commit autoupdate` bumps `rev` but not `args`, so
without this check the version actually run would drift silently behind `rev`.
"""

import re
import sys
from pathlib import Path


def _search(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def main(argv: list[str]) -> int:
    config = Path(argv[1]) if len(argv) > 1 else Path(".pre-commit-config.yaml")
    text = config.read_text(encoding="utf-8")
    rev = _search(r"rev:\s*lychee-v([0-9][0-9.]*)", text)
    arg = _search(r"LYCHEE_VERSION=([0-9][0-9.]*)", text)
    if rev is None and arg is None:
        return 0  # no lychee script hook configured
    if rev is None or arg is None:
        print(  # noqa: T201 # CLI checker, stderr is its report channel
            f"{config}: expected both 'rev: lychee-vX' and a 'LYCHEE_VERSION=X' hook "
            f"argument, found rev={rev!r} arg={arg!r}. Set both, or remove this "
            "check together with the lychee hook.",
            file=sys.stderr,
        )
        return 1
    if rev != arg:
        print(  # noqa: T201 # CLI checker, stderr is its report channel
            f"{config}: rev is lychee-v{rev} but the hook runs LYCHEE_VERSION={arg}. Make them match.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
