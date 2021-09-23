import re
import sys
from pathlib import Path
from typing import Set

from setuptools import find_packages, setup

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


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


# WEAK requirements (see requirements/python-dependencies.md)
PROD_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_base.in")
AIOHTTP_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_aiohttp.in")
FASTAPI_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_fastapi.in")

# STRONG requirements (see requirements/python-dependencies.md)
TEST_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_test.txt")


if __name__ == "__main__":

    setup(
        name="simcore-service-library",
        version="1.0.0",
        author="Pedro Crespo (pcrespov)",
        description="Core service library for simcore (or servicelib)",
        classifiers=[
            "Development Status :: 2 - Pre-Alpha",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Natural Language :: English",
            "Programming Language :: Python :: 3.8",
        ],
        long_description=Path(CURRENT_DIR / "README.rst").read_text(),
        license="MIT license",
        python_requires="~=3.8",
        install_requires=list(PROD_REQUIREMENTS),
        packages=find_packages(where="src"),
        package_dir={"": "src"},
        include_package_data=True,
        test_suite="tests",
        tests_require=list(TEST_REQUIREMENTS),
        extras_require={
            "test": list(TEST_REQUIREMENTS),
            "aiohttp": list(AIOHTTP_REQUIREMENTS),
            "fastapi": list(FASTAPI_REQUIREMENTS),
            "all": list(AIOHTTP_REQUIREMENTS | FASTAPI_REQUIREMENTS),
        },
        zip_safe=False,
    )
