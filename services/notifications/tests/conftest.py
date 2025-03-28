# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import pytest
from models_library.basic_types import BootModeEnum
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
]


@pytest.fixture
def mock_environment(monkeypatch: pytest.MonkeyPatch) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            "LOGLEVEL": "DEBUG",
            "SC_BOOT_MODE": BootModeEnum.DEBUG,
            "RABBIT_HOST": "test",
            "RABBIT_PASSWORD": "test",
            "RABBIT_SECURE": "false",
            "RABBIT_USER": "test",
        },
    )
