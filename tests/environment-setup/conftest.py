# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import sys
from pathlib import Path

## current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.pytest_global_environs",
]
