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


NAME = "simcore_service_dynamic_sidecar"
VERSION = (CURRENT_DIR / "VERSION").read_text().strip()
AUTHORS = "Andrei Neagu (GitHK), Sylvain Anderegg (sanderegg)"
DESCRIPTION = (
    "Implements a sidecar service to manage user's dynamic/interactive services"
)

# Hard requirements on third-parties and latest for in-repo packages
PROD_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-service-library[fastapi]",
        "simcore-settings-library",
    }
)

TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))


if __name__ == "__main__":
    from setuptools import find_packages, setup

    setup(
        name=NAME,
        version=VERSION,
        author=AUTHORS,
        description=DESCRIPTION,
        packages=find_packages(where="src"),
        package_dir={
            "": "src",
        },
        include_package_data=True,
        python_requires="~=3.8",
        PROD_REQUIREMENTS=PROD_REQUIREMENTS,
        TEST_REQUIREMENTS=TEST_REQUIREMENTS,
        setup_requires=["setuptools_scm"],
    )
