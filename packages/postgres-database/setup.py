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


# WEAK requirements
INSTALL_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_base.in"))

# STRICT requirements
MIGRATION_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_migration.in")
)
TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))


SETUP = dict(
    name="simcore-postgres-database",
    version=Path(CURRENT_DIR / "VERSION").read_text().strip(),
    author="Pedro Crespo (pcrespov)",
    description="Database models served by the simcore 'postgres' core service",
    # Get tags from https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
    ],
    long_description=Path(CURRENT_DIR / "README.md").read_text(),
    license="MIT license",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    test_suite="tests",
    install_requires=INSTALL_REQUIREMENTS,
    tests_require=TEST_REQUIREMENTS,
    extras_require={"migration": MIGRATION_REQUIREMENTS, "test": TEST_REQUIREMENTS},
    include_package_data=True,
    package_data={
        "": [
            "*.ini",
            "migration/*.py",
            "migration/*.mako",
            "migration/versions/*.py",
        ]
    },
    entry_points={
        "console_scripts": [
            "simcore-postgres-database=simcore_postgres_database.cli:main",
            "sc-pg=simcore_postgres_database.cli:main",
        ]
    },
    zip_safe=False,
)

if __name__ == "__main__":
    setup(**SETUP)
