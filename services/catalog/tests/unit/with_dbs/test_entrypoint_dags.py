# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict

import pytest
from fastapi import FastAPI
from respx.router import MockRouter
from simcore_service_catalog.meta import API_VERSION
from simcore_service_catalog.models.schemas.meta import Meta
from starlette.testclient import TestClient

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


def test_read_healthcheck(
    director_mockup: MockRouter, app: FastAPI, client: TestClient
):
    response = client.get("/")
    assert response.status_code == 200
    assert response.text


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
