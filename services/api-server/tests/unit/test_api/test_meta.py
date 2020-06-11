# pylint: disable=unused-variable
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from starlette.testclient import TestClient

from simcore_service_api_server.__version__ import api_version, api_vtag



def test_read_service_meta(client: TestClient):
    import pdb; pdb.set_trace()
    response = client.get(f"{api_vtag}/meta")
    assert response.status_code == 200
    assert response.json()["version"] == api_version
