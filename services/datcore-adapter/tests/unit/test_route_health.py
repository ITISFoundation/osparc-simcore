# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from datetime import datetime

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


def test_live_entrypoint(client: TestClient):
    response = client.get("/live")
    assert response.status_code == status.HTTP_200_OK
    assert response.text
    assert datetime.fromisoformat(response.text.split("@")[1])
    assert (
        response.text.split("@")[0]
        == "simcore_service_datcore_adapter.api.routes.health"
    )


def test_check_subsystem_health(client: TestClient):
    response = client.get("/ready")
