# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import logging

from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_api_server.core.settings import ApplicationSettings, BootModeEnum
from yarl import URL


def test_default_app_environ(app_environment: EnvVarsDict):
    # loads from environ
    settings = ApplicationSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.PRODUCTION
    assert settings.log_level == logging.DEBUG

    assert URL(settings.API_SERVER_POSTGRES.dsn) == URL(
        "postgresql://test:test@127.0.0.1:5432/test"
    )


def test_light_app_environ(patched_light_app_environ: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.API_SERVER_POSTGRES is None
