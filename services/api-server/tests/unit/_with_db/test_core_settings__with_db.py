# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import logging

from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_api_server.core.settings import ApplicationSettings, BootModeEnum
from yarl import URL

pytest_simcore_core_services_selection = ["postgres"]


def test_unit_with_db_app_environment(app_environment: EnvVarsDict, postgres_env_vars_dict: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    print("captured settings: \n", settings.model_dump_json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.PRODUCTION
    assert settings.logging_level == logging.DEBUG

    assert URL(settings.API_SERVER_POSTGRES.dsn) == URL(
        f"postgresql://{postgres_env_vars_dict['POSTGRES_USER']}:{postgres_env_vars_dict['POSTGRES_PASSWORD']}@"
        f"{postgres_env_vars_dict['POSTGRES_HOST']}:{postgres_env_vars_dict['POSTGRES_PORT']}"
        f"/{postgres_env_vars_dict['POSTGRES_DB']}"
    )
