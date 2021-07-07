# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from models_library.basic_types import LogLevel
from simcore_service_director_v2.core.settings import AppSettings, BootModeEnum


def test_loading_env_devel_in_settings(project_env_devel_environment):

    # loads from environ
    settings = AppSettings.create_from_envs()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.SC_BOOT_MODE == BootModeEnum.DEBUG
    assert settings.LOG_LEVEL == LogLevel.DEBUG

    assert settings.POSTGRES.dsn == "postgresql://test:test@localhost:5432/test"
