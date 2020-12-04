import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

here = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def read_reqs(reqs_path: Path):
    return re.findall(
        r"(^[^#\n-][\w\[,\]]+[-~>=<.\w]*)", reqs_path.read_text(), re.MULTILINE
    )


install_requirements = read_reqs(here / "requirements" / "_base.txt") + [
    "simcore-models-library"
]  # STRICT requirements

test_requirements = read_reqs(
    here / "requirements" / "_test.txt"
)  # STRICT requirements

readme = Path(here / "README.md").read_text()

setup(
    name="simcore-service-integration",
    version="1.0.0",
    author="Pedro Crespo (pcrespov), Sylvain Anderegg (sanderegg), Katie Zhuang (KZzizzle)",
    description="Toolkit for service integration",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Framework :: Pytest",
    ],
    long_description=readme,
    python_requires=">=3.6, <3.7",
    license="MIT license",
    install_requires=install_requirements,
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require={},
    zip_safe=False,
    entry_points={
        "console_scripts": ["simcore-service-integrator=service_integration.cli:main"],
        "pytest11": ["simcore_service_integration = service_integration.pytest_plugin"],
    },
)
