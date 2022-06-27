# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import simcore_service_storage._meta
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.app_diagnostics import AppStatusCheck
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_storage.handlers_health import HealthCheck

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


async def test_health_check(client: TestClient):
    assert client.app
    url = client.app.router["health_check"].url_for()
    response = await client.get(f"{url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert data
    assert not error

    app_health = HealthCheck.parse_obj(data)
    assert app_health.name == simcore_service_storage._meta.app_name
    assert app_health.version == simcore_service_storage._meta.api_version


async def test_health_status(client: TestClient):
    assert client.app
    url = client.app.router["get_status"].url_for()
    response = await client.get(f"{url}")
    data, error = await assert_status(response, web.HTTPOk)
    assert data
    assert not error

    app_status_check = AppStatusCheck.parse_obj(data)
    assert app_status_check.app_name == simcore_service_storage._meta.app_name
    assert app_status_check.version == simcore_service_storage._meta.api_version
    assert len(app_status_check.services) == 1
    assert "postgres" in app_status_check.services
    assert "healthy" in app_status_check.services["postgres"]
    assert app_status_check.services["postgres"]["healthy"] == True
