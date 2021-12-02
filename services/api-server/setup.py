#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path
from typing import Set

from setuptools import find_packages, setup


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


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

NAME = "simcore-service-api-server"
VERSION = (CURRENT_DIR / "VERSION").read_text().strip()
AUTHORS = "Pedro Crespo-Valero (pcrespov)"
DESCRIPTION = "Platform's API Server for external clients"
README = (CURRENT_DIR / "README.md").read_text()

PROD_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-sdk",
        "simcore-service-library[fastapi]",
        "simcore-settings-library",
    }
)

TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))

SETUP = dict(
    name=NAME,
    version=VERSION,
    author=AUTHORS,
    description=DESCRIPTION,
    long_description=README,
    license="MIT license",
    python_requires="~=3.8",
    packages=find_packages(where="src"),
    package_dir={
        "": "src",
    },
    include_package_data=True,
    package_data={
        "": [
            "mocks/*.y*ml",
        ]
    },
    install_requires=PROD_REQUIREMENTS,
    test_suite="tests",
    tests_require=TEST_REQUIREMENTS,
    extras_require={"test": TEST_REQUIREMENTS},
    entry_points={
        "console_scripts": [
            "simcore-service-api-server = simcore_service_api_server.cli:main",
        ],
    },
)

if __name__ == "__main__":
    setup(**SETUP)
