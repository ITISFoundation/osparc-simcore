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

VERSION = (CURRENT_DIR / "VERSION").read_text().strip()

PROD_REQUIREMENTS = list(
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-sdk",
        "simcore-service-library[fastapi]",
    }
)

TEST_REQUIREMENTS = list(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))

if __name__ == "__main__":
    setup(
        name="simcore-service-api-server",
        version=VERSION,
        author="Pedro Crespo (pcrespov)",
        description="Platform's API Server for external clients",
        classifiers=[
            "Development Status :: 1 - Planning",
            "License :: OSI Approved :: MIT License",
            "Natural Language :: English",
            "Programming Language :: Python :: 3.8",
        ],
        long_description=(CURRENT_DIR / "README.md").read_text(),
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
    )
