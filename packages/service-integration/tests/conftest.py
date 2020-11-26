# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict

import models_library
import pytest

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
]


@pytest.fixture(scope="session")
def package_dir():
    pdir = Path(models_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir
