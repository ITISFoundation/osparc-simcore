# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.api_schemas_directorv2.services import (
    ServiceExtras,
)
from pydantic import TypeAdapter
from respx import MockRouter


@pytest.fixture
def mock_engine(app: FastAPI) -> None:
    app.state.engine = AsyncMock()


async def test_get_service_extras(
    repository_lifespan_disabled: None,
    mocked_director_rest_api: MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    background_task_lifespan_disabled: None,
    mock_engine: None,
    mock_service_extras: ServiceExtras,
    aclient: AsyncClient,
):
    service_key = "simcore/services/comp/ans-model"
    service_version = "3.0.0"
    result = await aclient.get(f"/v0/services/{service_key}/{service_version}/extras")
    assert result.status_code == status.HTTP_200_OK, result.text

    assert (
        TypeAdapter(ServiceExtras).validate_python(result.json()) == mock_service_extras
    )
