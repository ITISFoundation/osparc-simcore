# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from starlette.testclient import TestClient


from fastapi import FastAPI


@pytest.fixture
def app(monkeypatch) -> FastAPI:
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # NOTE: keep import inside so monkey-patch has an effect
    from simcore_service_api_server.main import init_application
    app = init_application()

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:

    import pdb; pdb.set_trace()
    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli
