# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import httpx
from settings_library.rabbit import RabbitSettings
from starlette import status

pytest_simcore_core_services_selection = ["rabbit"]
pytest_simcore_ops_services_selection = []


async def test_healthcheck(rabbit_service: RabbitSettings, client: httpx.AsyncClient):
    response = await client.get("/")
    response.raise_for_status()
    assert response.status_code == status.HTTP_200_OK
    assert "simcore_service_efs_guardian" in response.text
