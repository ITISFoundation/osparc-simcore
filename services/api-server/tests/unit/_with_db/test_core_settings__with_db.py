# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import logging

from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_api_server.core.settings import ApplicationSettings, BootModeEnum
from yarl import URL


def test_unit_with_db_app_environment(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    print("captured settings: \n", settings.model_dump_json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.PRODUCTION
    assert settings.log_level == logging.DEBUG

    assert URL(settings.API_SERVER_POSTGRES.dsn) == URL(
        "postgresql://test:test@127.0.0.1:5432/test"
    )
