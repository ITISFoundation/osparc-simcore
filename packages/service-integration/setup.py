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

INSTALL_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt") | {"simcore-models-library"}
)  # STRICT requirements

TEST_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_test.txt")
)  # STRICT requirements


SETUP = dict(
    name="simcore-service-integration",
    version=Path(CURRENT_DIR / "VERSION").read_text().strip(),
    author=", ".join(
        (
            "Pedro Crespo-Valero (pcrespov)",
            "Sylvain Anderegg (sanderegg)",
            "Katie Zhuang (KZzizzle)",
            "Andrei Neagu (GitHK)",
        )
    ),
    description="Toolkit for service integration",
    classifiers=[
        "Development Status :: 4 - Beta",
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
            "osparc-service-integrator=service_integration.cli:main",
            "ooil=service_integration.cli:main",
        ],
        "pytest11": ["simcore_service_integration=service_integration.pytest_plugin"],
    },
)


if __name__ == "__main__":
    setup(**SETUP)
