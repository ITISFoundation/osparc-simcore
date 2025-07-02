from typing import Any

import pytest
from fastapi import status
from httpx import AsyncClient, BasicAuth
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.async_jobs_server import AsyncJobSideEffects
from simcore_service_api_server.models.schemas.tasks import ApiServerEnvelope


@pytest.fixture
async def async_jobs_rpc_side_effects() -> Any:
    return AsyncJobSideEffects()


@pytest.fixture
def mocked_async_jobs_rpc_api(
    mocker: MockerFixture,
    async_jobs_rpc_side_effects: Any,
    mocked_app_dependencies: None,
) -> dict[str, MockType]:
    """
    Mocks the catalog's simcore service RPC API for testing purposes.
    """
    from servicelib.rabbitmq.rpc_interfaces.async_jobs import async_jobs

    mocks = {}

    # Get all callable methods from the side effects class that are not built-ins
    side_effect_methods = [
        method_name
        for method_name in dir(async_jobs_rpc_side_effects)
        if not method_name.startswith("_")
        and callable(getattr(async_jobs_rpc_side_effects, method_name))
    ]

    # Create mocks for each method in catalog_rpc that has a corresponding side effect
    for method_name in side_effect_methods:
        assert hasattr(async_jobs, method_name)
        mocks[method_name] = mocker.patch.object(
            async_jobs,
            method_name,
            autospec=True,
            side_effect=getattr(async_jobs_rpc_side_effects, method_name),
        )

    return mocks


async def test_get_async_jobs(
    client: AsyncClient, mocked_async_jobs_rpc_api: dict[str, MockType], auth: BasicAuth
):

    response = await client.get("/v0/tasks", auth=auth)
    assert response.status_code == status.HTTP_200_OK
    ApiServerEnvelope[list[TaskGet]].model_validate_json(response.text)
    assert mocked_async_jobs_rpc_api["list_jobs"].called
