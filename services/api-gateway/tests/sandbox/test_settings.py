# import pytest
import logging
from pprint import pprint

from simcore_service_api_gateway.core.config import URL, AppSettings, BootModeEnum


def test_app_settings(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    settings = AppSettings()

    pprint(settings.dict())
    assert settings.boot_mode == BootModeEnum.production
    assert settings.postgres_dsn == URL("postgresql://test:test@localhost:5432/test")
    assert settings.loglevel == logging.DEBUG
