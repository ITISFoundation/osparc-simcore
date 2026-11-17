#!/usr/bin/env python3
"""Fail the commit unless the lychee hook's LYCHEE_VERSION argument matches its rev.

The lychee script hook must receive LYCHEE_VERSION=<rev version> as its first
argument, otherwise it infers its version with `git describe`. That inference
fails during `git commit` because git exports GIT_DIR into hooks and the
describe then targets this repository instead of the hook's cache clone.
`pre-commit autoupdate` bumps `rev` but not `args`, so without this check the
version actually run would drift silently behind `rev`.
"""

import os
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
        return os.EX_OK  # no lychee script hook configured
    if rev is None or arg is None:
        print(  # noqa: T201 # CLI checker, stderr is its report channel
            f"{config}: expected both 'rev: lychee-vX' and a 'LYCHEE_VERSION=X' hook "
            f"argument, found rev={rev!r} arg={arg!r}. Set both, or remove this "
            "check together with the lychee hook.",
            file=sys.stderr,
        )
        return os.EX_DATAERR
    if rev != arg:
        print(  # noqa: T201 # CLI checker, stderr is its report channel
            f"{config}: rev is lychee-v{rev} but the hook runs LYCHEE_VERSION={arg}. Make them match.",
            file=sys.stderr,
        )
        return os.EX_DATAERR
    return os.EX_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
