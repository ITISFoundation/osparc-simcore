# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import logging

import pytest
from simcore_service_director_v2.core.settings import (
    AppSettings,
    BootModeEnum,
    RegistrySettings,
)
from simcore_service_director_v2.modules.dynamic_sidecar.config import (
    DynamicSidecarSettings,
)


def test_loading_env_devel_in_settings(project_env_devel_environment):

    # loads from environ
    settings = AppSettings.create_from_env()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.boot_mode == BootModeEnum.DEBUG
    assert settings.loglevel == logging.DEBUG

    assert settings.postgres.dsn == "postgresql://test:test@localhost:5432/test"


def test_create_registry_settings():
    settings = RegistrySettings(
        url="http://registry:5000", auth=True, user="admin", pw="adminadmin", ssl=True
    )

    # http -> https
    assert settings.api_url == "https://registry:5000/v2"


@pytest.mark.parametrize("user,password", [(None, "pwd"), ("usr", None), (None, None)])
def test_registry_settings_error_missing_credentials(user, password):
    with pytest.raises(
        ValueError, match="Cannot authenticate without credentials user, pw"
    ):
        RegistrySettings(
            url="http://registry:5000", auth=True, user=user, pw=password, ssl=False
        )


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
    settings = DynamicSidecarSettings(image=image)
    assert settings.image == image
