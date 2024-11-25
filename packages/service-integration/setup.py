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

# NOTE on requirements:
#
# This package can be used either as a 'library' or an isolated 'executable'.
# In the first case, the requirements should not be strict in order to facilitate
# integrating with other libraries. In the latter, strict requirements are desirable
# since we value reproduciability and the code will be as in the tests.
#
# Depending on the case, we suggest two installation methods:
#
# - as a library: use directly pip
#       pip install .
# - as an executable: use recipe to install frozen dependencies and the pip installs library
#       make install-prod
#

INSTALL_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.in") | {"simcore-models-library"}
)

TEST_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_test.txt")
)  # STRICT requirements


SETUP = {
    "name": "simcore-service-integration",
    "version": Path(CURRENT_DIR / "VERSION").read_text().strip(),
    "author": ", ".join(
        (
            "Pedro Crespo-Valero (pcrespov)",
            "Sylvain Anderegg (sanderegg)",
            "Katie Zhuang (KZzizzle)",
            "Andrei Neagu (GitHK)",
        )
    ),
    "description": "Toolkit for service integration",
    "classifiers": [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.10",
        "Framework :: Pytest",
    ],
    "long_description": Path(CURRENT_DIR / "README.md").read_text(),
    "python_requires": "~=3.11",
    "license": "MIT license",
    "install_requires": INSTALL_REQUIREMENTS,
    "packages": find_packages(where="src"),
    "package_dir": {"": "src"},
    "include_package_data": True,
    "package_data": {
        "": [
            "py.typed",
            "service/tests/**/*.py",
            "service/tests/unit/*.py",
        ]
    },
    "test_suite": "tests",
    "tests_require": TEST_REQUIREMENTS,
    "extras_require": {},
    "zip_safe": False,
    "entry_points": {
        "console_scripts": [
            "ooil=service_integration.cli:app",
            "osparc-service-integrator=service_integration.cli:app",
            "simcore-service=service_integration.cli:app",
            "simcore-service-integrator=service_integration.cli:app",
        ],
        "pytest11": ["simcore_service_integration=service_integration.pytest_plugin"],
    },
}


if __name__ == "__main__":
    setup(**SETUP)
