# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import simcore_service_storage._meta
from aiohttp.test_utils import TestClient
from simcore_service_storage.app_handlers import HealthCheck

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_health_check(client: TestClient):
    resp = await client.get("/v0/")
    text = await resp.text()

    assert resp.status == 200, text

    payload = await resp.json()
    data, error = tuple(payload.get(k) for k in ("data", "error"))

    assert data
    assert not error

    app_health = HealthCheck.parse_obj(data)
    assert app_health.name == simcore_service_storage._meta.app_name
    assert app_health.version == simcore_service_storage._meta.api_version
