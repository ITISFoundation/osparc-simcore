# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.api_schemas_catalog.services import ServiceExtras
from respx import MockRouter


@pytest.fixture
def mock_engine(app: FastAPI) -> None:
    app.state.engine = AsyncMock()


async def test_get_service_extras(
    postgres_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    background_tasks_setup_disabled: None,
    mock_engine: None,
    mock_service_extras: ServiceExtras,
    aclient: AsyncClient,
):
    service_key = "simcore/services/comp/ans-model"
    service_version = "3.0.0"
    result = await aclient.get(f"/v0/services/{service_key}/{service_version}/extras")
    assert result.status_code == status.HTTP_200_OK, result.text
    assert result.json() == mock_service_extras.model_dump(mode="json")
