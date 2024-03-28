#!/bin/env python

import pathlib as pl
import platform
import sys


def main():
    major_v, minor_v, patch_v = platform.python_version_tuple()

    print(f"Found python version: {major_v}.{minor_v}.{patch_v}")

    min_major_v, min_minor_v = to_version(
        (pl.Path(__file__).parent.parent / "requirements" / "PYTHON_VERSION")
        .read_text()
        .strip()
    )

    exit_code = (
        1
        if int(major_v) < min_major_v
        or (int(major_v) == min_major_v and int(minor_v) < min_minor_v)
        else 0
    )

    if exit_code > 0:
        print(
            f"Wrong python version, osparc compilation needs at least Python {min_major_v}.{min_minor_v}"
        )

    sys.exit(exit_code)


def to_version(version):
    return tuple(int(v) for v in version.split("."))


if __name__ == "__main__":
    main()
