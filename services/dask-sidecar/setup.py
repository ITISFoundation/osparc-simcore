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

INSTALL_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_base.txt"))
TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))


SETUP = dict(
    name="simcore-service-dask-sidecar",
    version=(CURRENT_DIR / "VERSION").read_text().strip(),
    author="Pedro Crespo-Valero (pcrespov)",
    description="A dask-worker that runs as a sidecar",
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
    install_requires=INSTALL_REQUIREMENTS,
    test_suite="tests",
    tests_require=TEST_REQUIREMENTS,
    extras_require={"test": TEST_REQUIREMENTS},
)


if __name__ == "__main__":
    setup(**SETUP)
