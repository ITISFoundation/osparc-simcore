# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from pathlib import Path

import dotenv
import pytest
from pytest import MonkeyPatch


@pytest.fixture(scope="session")
def env_devel_dict(env_devel_file: Path) -> dict[str, str]:
    assert env_devel_file.exists()
    assert env_devel_file.name == ".env-devel"
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    assert all(v is not None for v in environ.values())
    return environ  # type: ignore


@pytest.fixture(scope="function")
def mock_env_devel_environment(
    env_devel_dict: dict[str, str], monkeypatch: MonkeyPatch
) -> dict[str, str]:
    for key, value in env_devel_dict.items():
        monkeypatch.setenv(key, str(value))
    return deepcopy(env_devel_dict)
