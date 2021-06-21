# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from datetime import datetime

import httpx
import pytest
from starlette import status
from starlette.testclient import TestClient


def test_live_entrypoint(client: TestClient):
    response = client.get("/live")
    assert response.status_code == status.HTTP_200_OK
    assert response.text
    assert datetime.fromisoformat(response.text.split("@")[1])
    assert (
        response.text.split("@")[0]
        == "simcore_service_datcore_adapter.api.routes.health"
    )


@pytest.mark.asyncio
async def test_check_subsystem_health(async_client: httpx.AsyncClient):
    response = await async_client.get("/ready")
