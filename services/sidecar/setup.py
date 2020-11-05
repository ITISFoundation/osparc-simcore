import re
import sys
from pathlib import Path

from setuptools import find_packages, setup

if sys.version_info.major != 3 and sys.version_info.minor >= 6:
    raise RuntimeError(
        "Expected ~=3.6, got %s (Tip: did you forget to 'source .venv/bin/activate' or 'pyenv local'?)"
        % str(sys.version_info)
    )

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def read_reqs(reqs_path: Path):
    return re.findall(r"(^[^#-][\w]+[-~>=<.\w]+)", reqs_path.read_text(), re.MULTILINE)


readme = (current_dir / "README.md").read_text()
version = (current_dir / "VERSION").read_text().strip()

install_requirements = read_reqs(current_dir / "requirements" / "_base.txt") + [
    "s3wrapper==0.1.0",
    "simcore-postgres-database",
    "simcore-sdk==0.1.0",
    "simcore-service-library",
    "simcore-models-library",
]

test_requirements = read_reqs(current_dir / "requirements" / "_test.txt") + [
    "simcore-postgres-database[migration]"
]


setup(
    name="simcore-service-sidecar",
    version=version,
    author="Sylvain Anderegg (sanderegg)",
    description="Platform's sidecar",
    classifiers={
        "Development Status :: 1 - Planning",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
    },
    long_description=readme,
    license="MIT license",
    python_requires="~=3.6",
    packages=find_packages(where="src"),
    package_dir={
        "": "src",
    },
    include_package_data=True,
    install_requires=install_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    extras_require={"test": test_requirements},
    entry_points={
        "console_scripts": [
            "simcore-service-sidecar = simcore_service_sidecar.cli:main",
        ],
    },
)
