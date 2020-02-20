import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
readme = Path(current_dir / "README.md").read_text()
version = Path(current_dir / "VERSION").read_text().strip()


def read_reqs(reqs_path: Path):
    return re.findall(r"(^[^#-][\w]+[-~>=<.\w]+)", reqs_path.read_text(), re.MULTILINE)


# Weak dependencies
install_requirements = read_reqs(current_dir / "requirements" / "_base.in")

# Strong dependencies
migration_requirements = read_reqs(current_dir / "requirements" / "_migration.txt")
test_requirements = read_reqs(current_dir / "requirements" / "_test.txt")


setup(
    name="simcore-postgres-database",
    version=version,
    author="Pedro Crespo (pcrespov)",
    description="Database models served by the simcore 'postgres' core service",
    # Get tags from https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
    ],
    long_description=readme,
    license="MIT license",
    packages=find_packages(wcurrent_dir="src"),
    package_dir={"": "src"},
    test_suite="tests",
    install_requires=install_requirements,
    tests_require=test_requirements,
    extras_require={"migration": migration_requirements, "test": test_requirements},
    include_package_data=True,
    package_data={
        "": ["*.ini", "migration/*.py", "migration/*.mako", "migration/versions/*.py",]
    },
    entry_points={
        "console_scripts": [
            "simcore-postgres-database=simcore_postgres_database.cli:main",
            "sc-pg=simcore_postgres_database.cli:main",
        ]
    },
    zip_safe=False,
)
