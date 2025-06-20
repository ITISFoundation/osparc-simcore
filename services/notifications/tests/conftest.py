# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


from pathlib import Path

import pytest
from models_library.basic_types import BootModeEnum
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.postgres_service",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "notifications"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_notifications"))
    return service_folder


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_environment_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_environment_dict,
            "LOGLEVEL": "DEBUG",
            "SC_BOOT_MODE": BootModeEnum.DEBUG,
        },
    )
