# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pathlib import Path

import pytest

from .helpers.typing_env import EnvVarsDict
from .helpers.utils_envs import load_dotenv, setenvs_from_dict


@pytest.fixture(scope="session")
def env_devel_dict(env_devel_file: Path) -> EnvVarsDict:
    assert env_devel_file.exists()
    assert env_devel_file.name == ".env-devel"
    return load_dotenv(env_devel_file, verbose=True, interpolate=True)


@pytest.fixture
def mock_env_devel_environment(
    env_devel_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    return setenvs_from_dict(monkeypatch, env_devel_dict)
