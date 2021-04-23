# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import logging

from simcore_service_api_server.core.settings import AppSettings, BootModeEnum
from yarl import URL


def test_min_environ_for_settings(project_env_devel_environment, monkeypatch):
    # Adds Dockerfile environs
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # loads from environ
    settings = AppSettings.create_from_env()
    print("captured settings: \n", settings.json(indent=2))

    assert settings.boot_mode == BootModeEnum.PRODUCTION
    assert settings.loglevel == logging.DEBUG

    assert URL(settings.postgres.dsn) == URL(
        "postgresql://test:test@127.0.0.1:5432/test"
    )
