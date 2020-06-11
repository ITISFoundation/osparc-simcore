# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def app(monkeypatch, enable_db) -> FastAPI:

    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("POSTGRES_ENABLED", str(enable_db))

    monkeypatch.setenv("LOGLEVEL", "debug")

    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # NOTE: keep import inside so monkey-patch has an effect
    from simcore_service_api_server.main import init_application

    app = init_application()

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli
