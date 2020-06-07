# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import pytest
from starlette.testclient import TestClient

from simcore_service_api_gateway.__version__ import api_version, api_vtag
from simcore_service_api_gateway.main import init_application


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # app
    app = init_application()

    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli


def test_read_service_meta(client: TestClient):
    response = client.get(f"{api_vtag}/meta")
    assert response.status_code == 200
    assert response.json()["version"] == api_version
