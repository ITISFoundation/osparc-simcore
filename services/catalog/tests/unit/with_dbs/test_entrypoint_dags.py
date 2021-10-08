# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from datetime import datetime
from random import randint
from typing import Any, Dict, List

import pytest
import simcore_service_catalog.api.dependencies.director
from fastapi import FastAPI
from models_library.services import ServiceDockerData, ServiceType
from respx.router import MockRouter
from simcore_service_catalog.api.routes import services
from simcore_service_catalog.meta import API_VERSION
from simcore_service_catalog.models.schemas.meta import Meta
from simcore_service_catalog.models.schemas.services import ServiceOut
from starlette.testclient import TestClient

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture(scope="session")
def registry_services() -> List[ServiceDockerData]:
    NUMBER_OF_SERVICES = 5
    return [
        ServiceDockerData(
            key="simcore/services/comp/my_comp_service",
            version=f"{v}.{randint(0,20)}.{randint(0,20)}",
            type=ServiceType.COMPUTATIONAL,
            name=f"my service {v}",
            description="a sleeping service version {v}",
            authors=[{"name": "me", "email": "me@myself.com"}],
            contact="me.myself@you.com",
            inputs=[],
            outputs=[],
        )
        for v in range(NUMBER_OF_SERVICES)
    ]


@pytest.fixture()
async def director_mockup(
    loop, monkeypatch, registry_services: List[ServiceOut], app: FastAPI
):
    async def return_list_services(user_id: int) -> List[ServiceOut]:
        return registry_services

    monkeypatch.setattr(services, "list_services", return_list_services)

    class FakeDirector:
        @staticmethod
        async def get(url: str):
            if url == "/services":
                return [s.dict(by_alias=True) for s in registry_services]
            if "/service_extras/" in url:
                return {
                    "build_date": f"{datetime.utcnow().isoformat(timespec='seconds')}Z"
                }

    def fake_director_api(*args, **kwargs):
        return FakeDirector()

    monkeypatch.setattr(
        simcore_service_catalog.api.dependencies.director,
        "get_director_api",
        fake_director_api,
    )

    # Check mock
    from simcore_service_catalog.api.dependencies.director import get_director_api

    assert isinstance(get_director_api(), FakeDirector)
    yield


def test_read_healthcheck(
    director_mockup: MockRouter, app: FastAPI, client: TestClient
):
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == '":-)"'


def test_read_meta(director_mockup: MockRouter, app: FastAPI, client: TestClient):
    response = client.get("/v0/meta")
    assert response.status_code == 200
    meta = Meta(**response.json())
    assert meta.version == API_VERSION
    assert meta.name == "simcore_service_catalog"


def test_list_dags(director_mockup: MockRouter, app: FastAPI, client: TestClient):
    response = client.get("/v0/dags")
    assert response.status_code == 200
    assert response.json() == []

    # inject three dagin
    response = client.get("/v0/dags")
    assert response.status_code == 200
    # TODO: assert i can list them as dagouts

    # TODO: assert dagout have identifiers now


@pytest.mark.skip(reason="does not work")
def test_standard_operations_on_resource(
    director_mockup: MockRouter,
    app: FastAPI,
    client: TestClient,
    fake_data_dag_in: Dict[str, Any],
):

    response = client.post("/v0/dags", json=fake_data_dag_in)
    assert response.status_code == 201
    assert response.json() == 1

    # list
    response = client.get("/v0/dags")
    assert response.status_code == 200
    got = response.json()

    assert isinstance(got, list)
    assert len(got) == 1

    # TODO: data_in is not the same as data_out??
    data_out = got[0]
    assert data_out["id"] == 1  # extra key, once in db

    # get
    response = client.get("/v0/dags/1")
    assert response.status_code == 200
    assert response.json() == data_out

    # delete
    response = client.delete("/v0/dags/1")
    assert response.status_code == 204
