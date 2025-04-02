# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
import json
from collections.abc import Iterator

import pytest
import respx
from fastapi import status
from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
from models_library.api_schemas_directorv2.dynamic_services import (
    DynamicServiceGet,
)
from pydantic import TypeAdapter
from simcore_service_dynamic_scheduler._meta import API_VTAG


@pytest.fixture
def mock_director_v2_service(
    running_services: list[DynamicServiceGet],
) -> Iterator[None]:
    with respx.mock(
        base_url="http://director-v2:8000/v2",
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get("/dynamic_services").respond(
            status.HTTP_200_OK,
            text=json.dumps(jsonable_encoder(running_services)),
        )

        yield None


@pytest.mark.parametrize(
    "running_services",
    [
        DynamicServiceGet.model_json_schema()["examples"],
        [],
    ],
)
async def test_running_services(mock_director_v2_service: None, client: AsyncClient):
    response = await client.get(f"/{API_VTAG}/ops/running-services")
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(
        TypeAdapter(list[DynamicServiceGet]).validate_python(response.json()), list
    )
