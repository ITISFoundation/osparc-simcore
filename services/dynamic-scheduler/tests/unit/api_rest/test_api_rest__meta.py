# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
from fastapi import status
from httpx import AsyncClient
from simcore_service_dynamic_scheduler._meta import API_VTAG
from simcore_service_dynamic_scheduler.models.schemas.meta import Meta


async def test_health(client: AsyncClient):
    response = await client.get(f"/{API_VTAG}/meta")
    assert response.status_code == status.HTTP_200_OK
    assert Meta.model_validate_json(response.text)
