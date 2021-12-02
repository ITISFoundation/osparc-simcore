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


PROD_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_base.txt") | {
    "simcore-models-library",
    "simcore-postgres-database",
    "simcore-service-library[aiohttp]",
    "simcore-settings-library",
}

TEST_REQUIREMENTS = read_reqs(CURRENT_DIR / "requirements" / "_test.txt")


SETUP = dict(
    name="simcore-service-storage",
    version="0.2.1",
    description="Service to manage data storage in simcore",
    author="Manuel Guidon (mguidon)",
    python_requires="~=3.8",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=PROD_REQUIREMENTS,
    tests_require=TEST_REQUIREMENTS,
    package_data={
        "": [
            "api/v0/openapi.yaml",
            "api/v0/schemas/*.json",
        ],
    },
    entry_points={
        "console_scripts": [
            "simcore-service-storage = simcore_service_storage.cli:main",
        ],
    },
)


if __name__ == "__main__":
    setup(**SETUP)
