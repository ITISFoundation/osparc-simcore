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

# Hard requirements on third-parties and latest for in-repo packages
PROD_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_base.txt"))

TEST_REQUIREMENTS = tuple(read_reqs(CURRENT_DIR / "requirements" / "_test.txt"))


SETUP = dict(
    name="simcore-service-image-puller",
    version=(CURRENT_DIR / "VERSION").read_text().strip(),
    author="Andrei Neagu (GitHK)",
    description="Service specialized in pulling images to the hosts",
    packages=find_packages(where="src"),
    package_dir={
        "": "src",
    },
    include_package_data=True,
    python_requires="~=3.9",
    PROD_REQUIREMENTS=PROD_REQUIREMENTS,
    TEST_REQUIREMENTS=TEST_REQUIREMENTS,
    setup_requires=["setuptools_scm"],
    entry_points={
        "console_scripts": [
            "image-puller=simcore_service_image_puller.main:main",
        ]
    },
)


if __name__ == "__main__":
    setup(**SETUP)
