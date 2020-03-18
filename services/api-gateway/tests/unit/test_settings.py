from simcore_service_api_gateway.settings import Settings, BootModeEnum, URL
import pytest
import logging
from pprint import pprint

def test_it(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    settings = Settings()

    pprint(settings.dict())
    assert settings.boot_mode == BootModeEnum.production
    assert settings.postgres_dsn == URL("postgresql://test:test@localhost:5432/test")
    assert settings.loglevel == logging.DEBUG
