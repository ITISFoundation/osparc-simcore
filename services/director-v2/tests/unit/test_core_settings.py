# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

import pytest
from models_library.basic_types import LogLevel
from simcore_service_director_v2.core.settings import (
    AppSettings,
    BootModeEnum,
    DynamicSidecarProxySettings,
    DynamicSidecarSettings,
)


def test_settings_with_project_env_devel(project_env_devel_environment):
    # loads from environ
    settings = AppSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.DEBUG
    assert settings.LOG_LEVEL == LogLevel.DEBUG

    assert settings.POSTGRES.dsn == "postgresql://test:test@localhost:5432/test"


def test_settings_with_env_devel(mock_env_devel_environment: Dict[str, str]):
    settings = AppSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))
    assert settings


@pytest.mark.parametrize(
    "image",
    [
        "local/dynamic-sidecar:development",
        "local/dynamic-sidecar:production",
        "itisfoundation/dynamic-sidecar:merge-github-testbuild-latest",
        "itisfoundation/dynamic-sidecar:1.0.0",
        "local/dynamic-sidecar:0.0.1",
        "dynamic-sidecar:production",
        "/dynamic-sidecar:latest",
        "/local/dynamic-sidecar:latest",
    ],
)
def test_dynamic_sidecar_settings(image: str) -> None:
    required_kwards = dict(
        DYNAMIC_SIDECAR_IMAGE=image,
        SIMCORE_SERVICES_NETWORK_NAME="test",
        TRAEFIK_SIMCORE_ZONE="",
        SWARM_STACK_NAME="",
        DYNAMIC_SIDECAR_PROXY_SETTINGS=DynamicSidecarProxySettings(),
    )
    settings = DynamicSidecarSettings(**required_kwards)

    assert settings.DYNAMIC_SIDECAR_IMAGE == image.lstrip("/")
