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

NAME = "simcore-service-library"
VERSION = "1.1.0"
AUTHORS = "Pedro Crespo-Valero (pcrespov)"
DESCRIPTION = "Core service library for simcore (or servicelib)"

# WEAK requirements (see requirements/python-dependencies.md)
PROD_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_base.in")
AIOHTTP_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_aiohttp.in")
FASTAPI_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_fastapi.in")

# STRONG requirements (see requirements/python-dependencies.md)
TEST_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_test.txt")


if __name__ == "__main__":
    from setuptools import find_packages, setup

    setup(
        name=NAME,
        version=VERSION,
        author=AUTHORS,
        description=DESCRIPTION,
        license="MIT license",
        python_requires="~=3.8",
        install_requires=tuple(PROD_REQUIREMENTS),
        packages=find_packages(where="src"),
        package_dir={"": "src"},
        test_suite="tests",
        tests_require=tuple(TEST_REQUIREMENTS),
        extras_require={
            "test": tuple(TEST_REQUIREMENTS),
            "aiohttp": tuple(AIOHTTP_REQUIREMENTS),
            "fastapi": tuple(FASTAPI_REQUIREMENTS),
            "all": tuple(AIOHTTP_REQUIREMENTS | FASTAPI_REQUIREMENTS),
        },
    )
