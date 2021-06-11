# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import logging

import pytest
from simcore_service_director_v2.core.settings import (
    AppSettings,
    BootModeEnum,
    DynamicSidecarSettings,
    RegistrySettings,
)


def test_loading_env_devel_in_settings(project_env_devel_environment):

    # loads from environ
    settings = AppSettings.create_from_env()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.boot_mode == BootModeEnum.DEBUG
    assert settings.loglevel == logging.DEBUG

    assert settings.postgres.dsn == "postgresql://test:test@localhost:5432/test"


@pytest.mark.parametrize(
    "image",
    [
        "local/dynamic-sidecar:development",
        "local/dynamic-sidecar:production",
        "itisfoundation/dynamic-sidecar:merge-github-testbuild-latest",
        "itisfoundation/dynamic-sidecar:1.0.0",
        "local/dynamic-sidecar:0.0.1",
        "dynamic-sidecar:production",
    ],
)
def test_dynamic_sidecar_settings(image: str) -> None:
    required_kwards = dict(
        simcore_services_network_name="test",
        traefik_simcore_zone="",
        swarm_stack_name="",
        registry=RegistrySettings(
            url="http://te.st", auth=True, user="test", password="test", ssl=False
        ),
    )
    required_kwards["image"] = image
    settings = DynamicSidecarSettings(**required_kwards)
    assert settings.image == image
