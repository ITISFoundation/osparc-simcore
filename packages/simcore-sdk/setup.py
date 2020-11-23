import re
import sys
from pathlib import Path

from setuptools import setup, find_packages

here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def read_reqs(reqs_path: Path):
    return re.findall(r"(^[^#-][\w]+[-~>=<.\w]+)", reqs_path.read_text(), re.MULTILINE)


install_requirements = read_reqs(here / "requirements" / "_base.in")
test_requirements = read_reqs(here / "requirements" / "_test.txt") + [
    "simcore-postgres-database[migration]",
    "simcore-service-library",
    "simcore-models-library",
    "s3wrapper",
    "simcore-service-storage-sdk",
]

setup(
    name="simcore-sdk",
    version="0.2.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.6",
    install_requires=install_requirements,
    tests_require=test_requirements,
    extras_require={"test": test_requirements},
    test_suite="tests",
)
