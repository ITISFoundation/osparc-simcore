# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from respx import MockRouter


@pytest.fixture
def mock_engine(app: FastAPI) -> None:
    app.state.engine = AsyncMock()


async def test_get_service_labels(
    postgres_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    background_tasks_setup_disabled: None,
    mock_engine: None,
    get_mocked_service_labels: Callable[[str, str], dict],
    aclient: AsyncClient,
):
    service_key = "simcore/services/comp/ans-model"
    service_version = "3.0.0"
    result = await aclient.get(f"/v0/services/{service_key}/{service_version}/labels")
    assert result.status_code == 200, result.text
    assert result.json() == get_mocked_service_labels(service_key, service_version)
