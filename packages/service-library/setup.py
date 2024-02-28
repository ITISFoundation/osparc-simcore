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


# WEAK requirements (see requirements/python-dependencies.md)
PROD_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_base.in")
AIOHTTP_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_aiohttp.in")
FASTAPI_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_fastapi.in")

# STRONG requirements (see requirements/python-dependencies.md)
TEST_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_test.txt")


SETUP = {
    "author": "Pedro Crespo-Valero (pcrespov)",
    "description": "Core service library for simcore (or servicelib)",
    "extras_require": {
        "aiohttp": tuple(AIOHTTP_REQUIREMENTS),
        "all": tuple(AIOHTTP_REQUIREMENTS | FASTAPI_REQUIREMENTS),
        "fastapi": tuple(FASTAPI_REQUIREMENTS),
        "test": tuple(TEST_REQUIREMENTS),
    },
    "install_requires": tuple(PROD_REQUIREMENTS),
    "license": "MIT license",
    "name": "simcore-service-library",
    "package_dir": {"": "src"},
    "packages": find_packages(where="src"),
    "python_requires": "~=3.10",
    "test_suite": "tests",
    "tests_require": tuple(TEST_REQUIREMENTS),
    "version": Path(CURRENT_DIR / "VERSION").read_text().strip(),
}


if __name__ == "__main__":
    setup(**SETUP)
