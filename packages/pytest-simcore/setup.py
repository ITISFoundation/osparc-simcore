import sys
from pathlib import Path

from setuptools import find_packages, setup

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

SETUP = {
    "name": "pytest-simcore",
    "version": Path(CURRENT_DIR / "VERSION").read_text().strip(),
    "author": ", ".join(
        (
            "Pedro Crespo-Valero (pcrespov)",
            "Sylvain Anderegg (sanderegg)",
        )
    ),
    "description": "pytest plugin with fixtures and test helpers for osparc-simcore repo modules",
    "py_modules": ["pytest_simcore"],
    # WARNING: this is used in frozen services as well !!!!
    "python_requires": "~=3.11",
    "install_requires": ["pytest>=3.5.0"],
    "extras_require": {
        "all": [
            "aio-pika",
            "aiohttp",
            "aioredis",
            "docker",
            "moto[server]",
            "python-socketio",
            "PyYAML",
            "sqlalchemy[postgresql_psycopg2binary]",
            "tenacity",
            "yarl",
        ],
    },
    "packages": find_packages(where="src"),
    "package_dir": {"": "src"},
    "classifiers": [
        "Development Status :: 4 - Beta",
        "Framework :: Pytest",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
    "entry_points": {"pytest11": ["simcore = pytest_simcore"]},
}


if __name__ == "__main__":
    setup(**SETUP)
