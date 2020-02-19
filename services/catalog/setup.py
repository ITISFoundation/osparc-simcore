#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

if sys.version_info.major != 3 and sys.version_info.minor != 6:
    raise RuntimeError(
        "Expected ~=3.6, got %s. Did you forget to activate virtualenv?"
        % str(sys.version_info)
    )

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def read_reqs(reqs_path: Path):
    return re.findall(r"(^[^#-][\w]+[-~>=<.\w]+)", reqs_path.read_text(), re.MULTILINE)


readme = (current_dir / "README.md").read_text()
version = (current_dir / "VERSION").read_text().strip()

install_requirements = read_reqs(current_dir / "requirements" / "_base.txt")

test_requirements = read_reqs(current_dir / "requirements" / "_test.txt")


setup(
    name="simcore-service-catalog",
    version=version,
    author="Pedro Crespo (pcrespov)",
    description="Manages and maintains a catalog of all published components (e.g. macro-algorithms, scripts, etc)",
    classifiers=[
        "Development Status :: 1 - Planning",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
    ],
    long_description=readme,
    license="MIT license",
    python_requires="~=3.6",
    packages=find_packages(where="src"),
    package_dir={"": "src",},
    package_data={"": ["config/*.yaml",],},
    include_package_data=True,
    install_requires=install_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require={"test": test_requirements},
    entry_points={
        "console_scripts": [
            "simcore-service-catalog = simcore_service_catalog.cli:main",
        ],
    },
)
