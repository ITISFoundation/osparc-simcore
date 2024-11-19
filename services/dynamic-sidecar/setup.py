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

# Hard requirements on third-parties and latest for in-repo packages
PROD_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-sdk>=1.1.0",
        "simcore-service-library[fastapi]",
        "simcore-settings-library",
    }
)

TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))


SETUP = {
    "name": "simcore-service-dynamic-sidecar",
    "version": (CURRENT_DIR / "VERSION").read_text().strip(),
    "author": ", ".join(
        (
            "Andrei Neagu (GitHK)",
            "Sylvain Anderegg (sanderegg)",
        )
    ),
    "description": "Implements a sidecar service to manage user's dynamic/interactive services",
    "packages": find_packages(where="src"),
    "package_dir": {
        "": "src",
    },
    "include_package_data": True,
    "python_requires": "~=3.11",
    "PROD_REQUIREMENTS": PROD_REQUIREMENTS,
    "TEST_REQUIREMENTS": TEST_REQUIREMENTS,
    "setup_requires": ["setuptools_scm"],
    "entry_points": {
        "console_scripts": [
            "simcore-service-dynamic-sidecar=simcore_service_dynamic_sidecar.cli:main",
            "simcore-service=simcore_service_dynamic_sidecar.cli:main",
        ],
    },
}


if __name__ == "__main__":
    setup(**SETUP)
