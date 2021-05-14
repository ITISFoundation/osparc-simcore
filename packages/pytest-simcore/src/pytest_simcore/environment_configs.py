# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from pathlib import Path
from typing import Dict, Union

import dotenv
import pytest


@pytest.fixture(scope="session")
def env_devel_dict(env_devel_file: Path) -> Dict[str, Union[str, None]]:
    assert env_devel_file.exists()
    assert env_devel_file.name == ".env-devel"
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture(scope="function")
def mock_env_testing_environ_varsment(env_devel_dict, monkeypatch):
    for key, value in env_devel_dict.items():
        monkeypatch.setenv(key, value)
    return deepcopy(env_devel_dict)
