# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import List

import pytest
from starlette.testclient import TestClient

# TODO: app is init globally ... which is bad!
from simcore_service_catalog.main import api_version, app


@pytest.fixture
def client(environ_context, postgres_service):
    # TODO: create new web-app everyt
    with TestClient(app) as cli:
        yield cli


def test_read_healthcheck(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "api_version" in response.json()
    assert response.json()["api_version"] == api_version


def test_standard_operations_on_resource(client, fake_data_dag_in):

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
