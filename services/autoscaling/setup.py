#!/usr/bin/env python3

import re
import sys
from pathlib import Path

from setuptools import find_packages, setup


def read_reqs(reqs_path: Path) -> set[str]:
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

NAME = "simcore-service-autoscaling"
VERSION = (CURRENT_DIR / "VERSION").read_text().strip()
AUTHORS = (
    "Alexandre Allexandre (Surfict)",
    "Sylvain Anderegg (sanderegg)",
    "Pedro Crespo-Valero (pcrespov)",
)
DESCRIPTION = "Service to autoscale swarm resources"
README = (CURRENT_DIR / "README.md").read_text()

PROD_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt")
    | {
        "simcore-models-library",
        "simcore-service-library[fastapi]",
        "simcore-settings-library",
    }
)

TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))

SETUP = {
    "name": NAME,
    "version": VERSION,
    "author": AUTHORS,
    "description": DESCRIPTION,
    "long_description": README,
    "license": "MIT license",
    "python_requires": "~=3.10",
    "packages": find_packages(where="src"),
    "package_dir": {
        "": "src",
    },
    "include_package_data": True,
    "install_requires": PROD_REQUIREMENTS,
    "test_suite": "tests",
    "tests_require": TEST_REQUIREMENTS,
    "extras_require": {"test": TEST_REQUIREMENTS},
    "entry_points": {
        "console_scripts": [
            "simcore-service-autoscaling = simcore_service_autoscaling.cli:main",
            "simcore-service = simcore_service_autoscaling.cli:main",
        ],
    },
}

if __name__ == "__main__":
    setup(**SETUP)
