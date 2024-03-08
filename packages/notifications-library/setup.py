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

INSTALL_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.in")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-settings-library",
    }
)  # WEAK requirements

TEST_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_test.txt") | {"pytest-simcore"}
)  # STRICT requirements


SETUP = {
    "name": "simcore-notifications-library",
    "version": Path(CURRENT_DIR / "VERSION").read_text().strip(),
    "author": "Pedro Crespo-Valero (pcrespov)",
    "description": "simcore library for user notifications e.g. emails, sms, etc",
    "python_requires": "~=3.10",
    "classifiers": [
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.10",
    ],
    "long_description": Path(CURRENT_DIR / "README.md").read_text(),
    "license": "MIT license",
    "install_requires": INSTALL_REQUIREMENTS,
    "packages": find_packages(where="src"),
    "package_dir": {"": "src"},
    "include_package_data": True,
    "package_data": {
        "": [
            "templates/**/*.jinja2",
            "templates/**/*.html",
            "templates/**/*.txt",
        ]
    },
    "test_suite": "tests",
    "tests_require": TEST_REQUIREMENTS,
    "extras_require": {"test": TEST_REQUIREMENTS},
    "zip_safe": False,
}


if __name__ == "__main__":
    setup(**SETUP)
