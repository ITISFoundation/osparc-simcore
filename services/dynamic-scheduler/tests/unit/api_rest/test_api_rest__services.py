# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.api_schemas_dynamic_scheduler.dynamic_services import (
    DynamicServiceStart,
    DynamicServiceStop,
)
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler._meta import API_VTAG
from simcore_service_dynamic_scheduler.services.service_tracker import (
    set_request_as_running,
    set_request_as_stopped,
)
from simcore_service_dynamic_scheduler.services.service_tracker._models import (
    UserRequestedState,
)

pytest_simcore_core_services_selection = [
    "redis",
]


@pytest.fixture
def app_environment(
    disable_rabbitmq_setup: None,
    disable_deferred_manager_setup: None,
    disable_notifier_setup: None,
    app_environment: EnvVarsDict,
    redis_service: RedisSettings,
    remove_redis_data: None,
) -> EnvVarsDict:
    return app_environment


async def _get_services(client: AsyncClient) -> dict[str, dict[str, Any]]:
    response = await client.get(f"/{API_VTAG}/services")
    assert response.status_code == status.HTTP_200_OK
    return response.json()


async def _remove_service(client: AsyncClient, node_id: NodeID) -> None:
    response = await client.delete(f"/{API_VTAG}/services/{node_id}")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.text == ""


async def test_services_api_workflow(
    client: AsyncClient,
    app: FastAPI,
    node_id: NodeID,
    get_dynamic_service_start: Callable[[NodeID], DynamicServiceStart],
    get_dynamic_service_stop: Callable[[NodeID], DynamicServiceStop],
):
    str_node_id = f"{node_id}"

    # request as running then as stopped
    assert await _get_services(client) == {}

    # SET AS RUNNING
    await set_request_as_running(app, get_dynamic_service_start(node_id))
    services = await _get_services(client)
    assert len(services) == 1
    assert services[str_node_id]["requested_state"] == UserRequestedState.RUNNING

    # SET AS STOPPED
    await set_request_as_stopped(app, get_dynamic_service_stop(node_id))
    services = await _get_services(client)
    assert len(services) == 1
    assert services[str_node_id]["requested_state"] == UserRequestedState.STOPPED

    # REMOVE SERVICE
    await _remove_service(client, node_id)
    assert await _get_services(client) == {}
