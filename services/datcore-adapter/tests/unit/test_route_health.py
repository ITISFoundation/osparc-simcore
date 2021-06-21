# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from fastapi.applications import FastAPI
from starlette import status
from starlette.testclient import TestClient


@pytest.fixture()
def minimal_app() -> FastAPI:
    from simcore_service_datcore_adapter.main import the_app

    return the_app


@pytest.fixture()
def client(minimal_app: FastAPI) -> TestClient:
    with TestClient(minimal_app) as cli:
        return cli


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.text
