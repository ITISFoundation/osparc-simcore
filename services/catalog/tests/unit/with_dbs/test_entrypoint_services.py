from starlette.testclient import TestClient

from simcore_service_catalog.models.domain.service import ServiceData


core_services = ["postgres", "director"]
ops_services = ["adminer"]


def test_list_services(client: TestClient):
    pass
    # response = client.get("/v0/services")
    # assert response.status_code == 200
