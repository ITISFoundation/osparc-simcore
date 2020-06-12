# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
from fastapi.testclient import TestClient

from simcore_service_api_server.__version__ import api_version, api_vtag
from simcore_service_api_server.models.schemas.meta import Meta


def test_read_service_meta(client: TestClient):
    response = client.get(f"{api_vtag}/meta")
    assert response.status_code == 200
    assert response.json()["version"] == api_version

    meta = Meta.parse_obj(response.json())
    assert meta.version == api_version
