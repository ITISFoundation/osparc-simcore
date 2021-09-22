#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path
from typing import Set

from setuptools import find_packages, setup

if not (sys.version_info.major == 3 and sys.version_info.minor == 8):
    raise RuntimeError(
        "Expected ~=3.8, got %s (Tip: did you forget to 'source .venv/bin/activate' or 'pyenv local'?)"
        % str(sys.version_info)
    )

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def read_reqs(reqs_path: Path) -> Set[str]:
    return {
        r
        for r in re.findall(
            r"(^[^#\n-][\w\[,\]]+[-~>=<.\w]*)",
            reqs_path.read_text(),
            re.MULTILINE,
        )
        if isinstance(r, str)
    }


readme = (current_dir / "README.md").read_text()
version = (current_dir / "VERSION").read_text().strip()

install_requirements = list(
    read_reqs(current_dir / "requirements" / "_base.txt")
    | read_reqs(current_dir / "requirements" / "_packages.txt")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-service-library[aiohttp]",
    }
)

test_requirements = read_reqs(current_dir / "requirements" / "_test.txt")

setup(
    name="simcore-service-catalog",
    version=version,
    author="Pedro Crespo (pcrespov)",
    description="Manages and maintains a catalog of all published components (e.g. macro-algorithms, scripts, etc)",
    # Get tags from https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
    ],
    long_description=readme,
    license="MIT license",
    python_requires="~=3.8",
    packages=find_packages(where="src"),
    package_dir={
        "": "src",
    },
    package_data={
        "": [
            "config/*.yaml",
        ],
    },
    include_package_data=True,
    # install_requires=install_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require={"test": test_requirements},
)
