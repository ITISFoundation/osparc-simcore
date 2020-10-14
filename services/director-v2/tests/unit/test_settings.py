# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import logging

from simcore_service_director_v2.core.settings import AppSettings, BootModeEnum
from yarl import URL


def test_loading_env_devel_in_settings(project_env_devel_environment, monkeypatch):

    # loads from environ
    settings = AppSettings.create_from_env()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.boot_mode == BootModeEnum.DEBUG
    assert settings.loglevel == logging.DEBUG

    assert settings.postgres.dsn == URL("postgresql://test:test@localhost:5432/test")
