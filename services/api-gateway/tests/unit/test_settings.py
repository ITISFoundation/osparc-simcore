from simcore_service_api_gateway.settings import Settings
import pytest
import logging


def test_it(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("LOGLEVEL", "debug")

    settings = Settings()

    assert settings.postgres_dsn == "postgresql://test:test@localhost:5432/test"
    assert settings.loglevel == logging.DEBUG
