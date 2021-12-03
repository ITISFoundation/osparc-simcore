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


# WEAK requirements (see requirements/python-dependencies.md)
PROD_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_base.in")
AIOHTTP_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_aiohttp.in")
FASTAPI_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_fastapi.in")

# STRONG requirements (see requirements/python-dependencies.md)
TEST_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_test.txt")


SETUP = dict(
    name="simcore-service-library",
    version=Path(CURRENT_DIR / "VERSION").read_text().strip(),
    author="Pedro Crespo-Valero (pcrespov)",
    description="Core service library for simcore (or servicelib)",
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


if __name__ == "__main__":
    setup(**SETUP)
