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
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt") | {"simcore-models-library"}
)  # STRICT requirements

TEST_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_test.txt")
)  # STRICT requirements


SETUP = dict(
    name="simcore-service-integration",
    version="1.0.0",
    author="Pedro Crespo (pcrespov), Sylvain Anderegg (sanderegg), Katie Zhuang (KZzizzle)",
    description="Toolkit for service integration",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.8",
        "Framework :: Pytest",
    ],
    long_description=Path(CURRENT_DIR / "README.md").read_text(),
    python_requires=">=3.6",
    license="MIT license",
    install_requires=INSTALL_REQUIREMENTS,
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    test_suite="tests",
    tests_require=TEST_REQUIREMENTS,
    extras_require={},
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "simcore-service-integrator=service_integration.cli:main",
            "oint=service_integration.cli:main",
        ],
        "pytest11": ["simcore_service_integration=service_integration.pytest_plugin"],
    },
)


if __name__ == "__main__":
    setup(**SETUP)
