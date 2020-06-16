# import pytest
import logging
from pprint import pprint

from simcore_service_api_server.core.settings import (
    URL,
    AppSettings,
    BootModeEnum,
    PostgresSettings,
    WebServerSettings,
)


# bring .env-devel in here
def test_min_environ_for_settings(monkeypatch):
    monkeypatch.setenv("WEBSERVER_HOST", "production_webserver")
    monkeypatch.setenv("WEBSERVER_SESSION_SECRET_KEY", "test")

    monkeypatch.setenv("POSTGRES_HOST", "production_postgres")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "simcoredb")

    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # NOTE: pg and weberver settings parse environ NOW!
    settings = AppSettings(postgres=PostgresSettings(), webserver=WebServerSettings())

    pprint(settings.dict())

    assert settings.boot_mode == BootModeEnum.production
    assert settings.loglevel == logging.DEBUG

    assert settings.postgres.dsn == URL(
        "postgresql://test:test@production_postgres:5432/simcoredb"
    )
