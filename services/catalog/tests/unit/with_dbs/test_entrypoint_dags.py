# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict, List

import pytest
from simcore_service_catalog.__version__ import api_version
from simcore_service_catalog.models.schemas.meta import Meta
from starlette.testclient import TestClient

core_services = ["postgres"]
ops_services = ["adminer"]


@pytest.mark.skip(reason="Failing on github actions")
def test_read_healthcheck(director_mockup, client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == '":-)"'


@pytest.mark.skip(reason="Failing on github actions")
def test_read_meta(director_mockup, client: TestClient):
    response = client.get("/v0/meta")
    assert response.status_code == 200
    meta = Meta(**response.json())
    assert meta.version == api_version
    assert meta.name == "simcore_service_catalog"


@pytest.mark.skip(reason="Failing on github actions")
def test_list_dags(director_mockup, client: TestClient):
    response = client.get("/v0/dags")
    assert response.status_code == 200
    assert response.json() == []

    # inject three dagin
    response = client.get("/v0/dags")
    assert response.status_code == 200
    # TODO: assert i can list them as dagouts

    # TODO: assert dagout have identifiers now


@pytest.mark.skip(reason="Failing on github actions")
def test_standard_operations_on_resource(
    director_mockup, client: TestClient, fake_data_dag_in: Dict
):

    response = client.post("/v0/dags", json=fake_data_dag_in)
    assert response.status_code == 201
    assert response.json() == 1

    # list
    response = client.get("/v0/dags")
    assert response.status_code == 200
    got = response.json()

    assert isinstance(got, List)
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
