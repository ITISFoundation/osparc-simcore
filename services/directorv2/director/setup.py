import os
import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

current_dir = Path(os.path.dirname(os.path.realpath(__file__)))


def read_reqs(reqs_path: Path):
    return re.findall(r"(^[^#-][\w]+[-~>=<.\w]+)", reqs_path.read_text(), re.MULTILINE)


# -----------------------------------------------------------------
# Hard requirements on third-parties and latest for in-repo packages
install_requirements = read_reqs(current_dir / "requirements" / "base.txt")
test_requirements = read_reqs(current_dir / "requirements" / "test.txt")

setup(
    name="director",
    version="0.2.0",
    packages=find_packages(where="src"),
    package_dir={"": "src",},
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=install_requirements,
    tests_require=test_requirements,
    setup_requires=["setuptools_scm"],
)
