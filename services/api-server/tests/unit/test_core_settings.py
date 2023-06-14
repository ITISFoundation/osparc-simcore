# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import logging

from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_api_server.core.settings import ApplicationSettings, BootModeEnum


def test_unit_app_environment(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.PRODUCTION
    assert settings.log_level == logging.DEBUG

    assert settings.API_SERVER_POSTGRES is None
