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


INSTALL_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_base.in"))
TEST_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_test.txt")
    | {
        "simcore-postgres-database",
        "simcore-service-library",
        "simcore-models-library",
    }
)

SETUP = dict(
    name="simcore-sdk",
    version=Path(CURRENT_DIR / "VERSION").read_text().strip(),
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.6",
    install_requires=INSTALL_REQUIREMENTS,
    tests_require=TEST_REQUIREMENTS,
    extras_require={"test": TEST_REQUIREMENTS},
    test_suite="tests",
)


if __name__ == "__main__":
    setup(**SETUP)
