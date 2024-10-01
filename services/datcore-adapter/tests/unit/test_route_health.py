# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from datetime import datetime

import httpx
import respx
from models_library.app_diagnostics import AppStatusCheck
from starlette import status


async def test_live_entrypoint(async_client: httpx.AsyncClient):
    response = await async_client.get("v0/live")
    assert response.status_code == status.HTTP_200_OK
    assert response.text
    assert datetime.fromisoformat(response.text.split("@")[1])
    assert (
        response.text.split("@")[0]
        == "simcore_service_datcore_adapter.api.routes.health"
    )


async def test_check_subsystem_health(async_client: httpx.AsyncClient):
    async with respx.mock:
        pennsieve_health_route = respx.get("https://api.pennsieve.io/health/").respond(
            status.HTTP_200_OK
        )
        response = await async_client.get("v0/ready")

        assert pennsieve_health_route.called
        assert response.status_code == status.HTTP_200_OK
        app_status = AppStatusCheck.model_validate(response.json())
        assert app_status
        assert app_status.app_name == "simcore-service-datcore-adapter"
        assert app_status.services == {"pennsieve": True}

    async with respx.mock:
        pennsieve_health_route = respx.get("https://api.pennsieve.io/health/")
        pennsieve_health_route.side_effect = [httpx.ConnectError]
        response = await async_client.get("v0/ready")

        assert pennsieve_health_route.called
        assert response.status_code == status.HTTP_200_OK
        app_status = AppStatusCheck.model_validate(response.json())
        assert app_status
        assert app_status.app_name == "simcore-service-datcore-adapter"
        assert app_status.services == {"pennsieve": False}
