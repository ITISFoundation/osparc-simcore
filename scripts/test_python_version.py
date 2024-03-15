#!/bin/env python

import platform
import sys


def main():
    major_v, minor_v, patch_v = platform.python_version_tuple()

    print(f"Found python version: {major_v}.{minor_v}.{patch_v}")

    exit_code = (
        1 if int(major_v) < 2 or (int(major_v) == 3 and int(minor_v) < 10) else 0
    )

    if exit_code > 0:
        print("Wrong python version, osparc compilation needs at least Python 3.10")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
