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


INSTALL_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.in")
)  # WEAK requirements

TEST_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_test.txt")
)  # STRICK requirements


SETUP = dict(
    name="simcore-models-library",
    version="0.1.0",
    author="Sylvain Anderegg (sanderegg)",
    description="Core service library for simcore pydantic models",
    python_requires="~=3.8",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
    ],
    long_description=Path(CURRENT_DIR / "README.md").read_text(),
    license="MIT license",
    install_requires=INSTALL_REQUIREMENTS,
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    test_suite="tests",
    tests_require=TEST_REQUIREMENTS,
    extras_require={"test": TEST_REQUIREMENTS},
    zip_safe=False,
)


if __name__ == "__main__":
    setup(**SETUP)
