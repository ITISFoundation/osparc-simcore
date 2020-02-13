# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
from starlette.testclient import TestClient


# TODO: app is init globally ... which is bad!
from simcore_service_catalog.main import __version__, app


@pytest.fixture
def client(environ_context, postgres_service):
    # TODO: create new web-app everyt
    cli = TestClient(app)
    return cli


def test_read_main(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "api_version" in response.json()
    assert response.json()['api_version'] == __version__
