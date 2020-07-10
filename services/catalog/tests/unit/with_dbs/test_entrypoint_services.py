# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import pytest
from starlette.testclient import TestClient

from simcore_service_catalog.models.domain.service import ServiceData

core_services = ["postgres"]
ops_services = ["adminer"]


@pytest.fixture()
def director_mockup(mocker):
    pass


def test_list_services(client: TestClient, director_mockup):
    response = client.get("/v0/services")
    assert response.status_code == 200
