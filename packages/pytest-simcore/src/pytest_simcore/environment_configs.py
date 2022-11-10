# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pathlib import Path

import pytest
from pytest import MonkeyPatch

from .helpers.typing_env import EnvVarsDict
from .helpers.utils_envs import load_dotenv, setenvs_from_dict


@pytest.fixture(scope="session")
def env_devel_dict(env_devel_file: Path) -> EnvVarsDict:
    assert env_devel_file.exists()
    assert env_devel_file.name == ".env-devel"
    envs = load_dotenv(env_devel_file, verbose=True, interpolate=True)
    return envs


@pytest.fixture(scope="function")
def mock_env_devel_environment(
    env_devel_dict: dict[str, str], monkeypatch: MonkeyPatch
) -> EnvVarsDict:
    envs = setenvs_from_dict(monkeypatch, env_devel_dict)
    return envs
