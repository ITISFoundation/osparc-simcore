# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import status
from fastapi.testclient import TestClient
from simcore_service_payments._meta import API_VTAG
from simcore_service_payments.models.schemas.meta import Meta


def test_healthcheck(client: TestClient):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.text.startswith("simcore_service_payments.api._health@")


def test_meta(client: TestClient):
    response = client.get(f"/{API_VTAG}/meta")
    assert response.status_code == status.HTTP_200_OK
    meta = Meta.parse_obj(response.json())

    response = client.get(meta.docs_url)
    assert response.status_code == status.HTTP_200_OK
