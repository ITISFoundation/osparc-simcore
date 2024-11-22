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
INSTALL_REQUIREMENTS = tuple(
    read_reqs(CURRENT_DIR / "requirements" / "_base.txt")
    | {
        "simcore-models-library",
        "simcore-postgres-database",
        "simcore-settings-library",
        "simcore-service-library[aiohttp]>=1.2.0",
    }
)
TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))

SETUP = {
    "name": "simcore-service-webserver",
    "version": Path(CURRENT_DIR / "VERSION").read_text().strip(),
    "description": "Main service with an interface (http-API & websockets) to the web front-end",
    "author": ", ".join(
        (
            "Pedro Crespo-Valero (pcrespov)",
            "Sylvain Anderegg (sanderegg)",
            "Andrei Neagu (GitHK)",
        )
    ),
    "packages": find_packages(where="src"),
    "package_dir": {
        "": "src",
    },
    "include_package_data": True,
    "package_data": {
        "": [
            "api/v0/openapi.yaml",
            "api/v0/schemas/*.json",
            "templates/**/*.jinja2",
        ]
    },
    "entry_points": {
        "console_scripts": [
            "simcore-service-webserver=simcore_service_webserver.__main__:main",
            "simcore-service=simcore_service_webserver.__main__:main",
        ]
    },
    "python_requires": "~=3.11",
    "install_requires": INSTALL_REQUIREMENTS,
    "tests_require": TEST_REQUIREMENTS,
    "setup_requires": ["pytest-runner"],
}


if __name__ == "__main__":
    setup(**SETUP)
