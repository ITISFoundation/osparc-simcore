import os
import re
from pathlib import Path

from setuptools import find_packages, setup

current_dir = Path(os.path.dirname(os.path.realpath(__file__)))


def read_reqs(reqs_path: Path):
    return re.findall(r"(^[^#-][\w]+[-~>=<.\w]+)", reqs_path.read_text(), re.MULTILINE)


# -----------------------------------------------------------------
# Hard requirements on third-parties and latest for in-repo packages
install_requires = read_reqs(current_dir / "requirements" / "_base.txt")
tests_require = read_reqs(current_dir / "requirements" / "_test.txt")

current_version = (current_dir / "VERSION").read_text().strip()

setup(
    name="scheduler",
    version=current_version,
    packages=find_packages(where="src"),
    package_dir={"": "src",},
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=install_requires,
    tests_require=tests_require,
    setup_requires=["setuptools_scm"],
    entry_points={
        "console_scripts": [
            "scheduler-startup = scheduler.main:main",
        ],
    },
)
