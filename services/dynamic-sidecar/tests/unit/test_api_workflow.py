# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=no-member


import asyncio
import json
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Final
from unittest.mock import AsyncMock

import pytest
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import AsyncClient
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingMessages,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
)
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import AnyHttpUrl, parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    TaskId,
    periodic_task_result,
)
from servicelib.fastapi.long_running_tasks.client import setup as client_setup
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.models.schemas.containers import ContainersCreate

_FAST_STATUS_POLL: Final[float] = 0.1
_CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60
_BASE_HEART_BEAT_INTERVAL: Final[float] = 0.1


@pytest.fixture
def compose_spec() -> str:
    return json.dumps(
        {
            "version": "3",
            "services": {
                "solo-box": {
                    "image": "alpine:latest",
                    "command": ["sh", "-c", "sleep 100000"],
                }
            },
        }
    )


@pytest.fixture
def backend_url() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://backgroud.testserver.io")


@pytest.fixture
def mock_environment(
    mock_core_rabbitmq: dict[str, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
    mock_environment: EnvVarsDict,
) -> EnvVarsDict:
    setenvs_from_dict(
        monkeypatch,
        {
            "LOG_LEVEL": "DEBUG",
            "RESOURCE_TRACKING_HEARTBEAT_INTERVAL": f"{_BASE_HEART_BEAT_INTERVAL}",
            "RABBIT_HOST": "mocked_host",
            "RABBIT_SECURE": "false",
            "RABBIT_USER": "mocked_user",
            "RABBIT_PASSWORD": "mocked_password",
        },
    )
    return mock_environment


@pytest.fixture
async def app(app: FastAPI) -> AsyncIterable[FastAPI]:
    # add the client setup to the same application
    # this is only required for testing, in reality
    # this will be in a different process
    client_setup(app)
    async with LifespanManager(app):
        yield app


@pytest.fixture
async def httpx_async_client(
    app: FastAPI,
    backend_url: AnyHttpUrl,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers: None,
    ensure_shared_store_dir: Path,
) -> AsyncIterable[AsyncClient]:
    # crete dir here
    async with AsyncClient(
        app=app, base_url=backend_url, headers={"Content-Type": "application/json"}
    ) as client:
        yield client


@pytest.fixture
def client(
    app: FastAPI, httpx_async_client: AsyncClient, backend_url: AnyHttpUrl
) -> Client:
    return Client(app=app, async_client=httpx_async_client, base_url=backend_url)


async def _get_task_id_create_service_containers(
    httpx_async_client: AsyncClient,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
) -> TaskId:
    containers_create = ContainersCreate(
        docker_compose_yaml=compose_spec, metrics_params=mock_metrics_params
    )
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers", json=containers_create.dict()
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_docker_compose_down(httpx_async_client: AsyncClient) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers:down")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


def _get_resource_tracking_messages(
    mock_core_rabbitmq: dict[str, AsyncMock]
) -> list[RabbitResourceTrackingMessages]:
    return [
        x[0][1]
        for x in mock_core_rabbitmq["post_rabbit_message"].call_args_list
        if isinstance(x[0][1], RabbitResourceTrackingMessages)
    ]


async def test_workflow_service_metrics__open_heartbeat_close(
    mock_core_rabbitmq: dict[str, AsyncMock],
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
    ) as result:
        assert isinstance(result, list)
        assert len(result) == 1

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_docker_compose_down(httpx_async_client),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
    ) as result:
        assert result is None

    # NOTE: task was not properly cancelled and events where still
    # generated. This is here to catch regressions.
    await asyncio.sleep(_BASE_HEART_BEAT_INTERVAL * 10)

    # Ensure messages arrive in the expected order
    resource_tracking_messages = _get_resource_tracking_messages(mock_core_rabbitmq)
    assert len(resource_tracking_messages) >= 3

    start_message = resource_tracking_messages[0]
    heart_beat_messages = resource_tracking_messages[1:-1]
    stop_message = resource_tracking_messages[-1]

    assert isinstance(start_message, RabbitResourceTrackingStartedMessage)
    for heart_beat_message in heart_beat_messages:
        assert isinstance(heart_beat_message, RabbitResourceTrackingHeartbeatMessage)
    assert isinstance(stop_message, RabbitResourceTrackingStoppedMessage)
