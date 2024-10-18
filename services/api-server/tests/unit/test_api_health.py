# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pathlib import Path

from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.app_diagnostics import AppStatusCheck
from respx import MockRouter
from simcore_service_api_server._meta import API_VTAG


async def test_check_service_health(
    mocker: MockRouter, client: AsyncClient, app: FastAPI
):
    class MockHealthChecker:
        @property
        def healthy(self) -> bool:
            return True

    app.state.health_checker = MockHealthChecker()
    response = await client.get(f"{API_VTAG}/")
    assert response.status_code == status.HTTP_200_OK
    assert "health" in response.text


async def test_get_service_state(
    client: AsyncClient,
    mocked_catalog_service_api_base: MockRouter,
    mocked_directorv2_service_api_base: MockRouter,
    mocked_storage_service_api_base: MockRouter,
    mocked_webserver_service_api_base: MockRouter,
):
    response = await client.get(f"{API_VTAG}/state")
    assert response.status_code == status.HTTP_200_OK

    version_file: Path = Path(__file__).parent.parent.parent / "VERSION"
    assert version_file.is_file()

    assert response.json() == {
        "app_name": "simcore-service-api-server",
        "version": version_file.read_text().strip(),
        "services": {
            "catalog": {"healthy": True},
            "director_v2": {"healthy": True},
            "storage": {"healthy": True},
            "webserver": {"healthy": True},
        },
        "url": "http://api.testserver.io/state",
    }

    assert AppStatusCheck.model_validate(response.json())
