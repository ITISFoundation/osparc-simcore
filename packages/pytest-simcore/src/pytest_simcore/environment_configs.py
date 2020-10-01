# pylint: disable=redefined-outer-name

from pathlib import Path
from typing import Dict

import pytest

from .helpers.utils_environs import load_env


@pytest.fixture(scope="session")
def env_devel_config(env_devel_file: Path) -> Dict[str,str]:
    env_devel = {}
    # TODO: use instead from dotenv import dotenv_values
    # env_devel = dotenv_values(env_devel_file, verbose=True, interpolate=True)
    with env_devel_file.open() as f:
        env_devel = load_env(f)
    return env_devel
