#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path
from typing import Set


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
    | read_reqs(CURRENT_DIR / "requirements" / "_packages.txt")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-service-library[fastapi]",
    }
)

TEST_REQUIREMENTS = list(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))


if __name__ == "__main__":
    from setuptools import find_packages, setup

    setup(
        name="simcore-service-catalog",
        version=VERSION,
        author="Pedro Crespo (pcrespov)",
        description="Manages and maintains a catalog of all published components (e.g. macro-algorithms, scripts, etc)",
        # Get tags from https://pypi.org/classifiers/
        classifiers=[
            "Development Status :: 3 - Alpha",
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
        install_requires=PROD_REQUIREMENTS,
        test_suite="tests",
        tests_require=TEST_REQUIREMENTS,
        extras_require={"test": TEST_REQUIREMENTS},
    )
