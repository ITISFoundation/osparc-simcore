# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

from typing import AsyncIterator

import pytest
from aiodocker import DockerError
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCNamespace
from settings_library.rabbit import RabbitSettings
from simcore_service_agent.core.application import create_app
from simcore_service_agent.core.settings import ApplicationSettings

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
async def initialized_app(
    rabbit_service: RabbitSettings, env: None
) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app()

    await app.router.startup()
    yield app
    await app.router.shutdown()


@pytest.fixture
async def test_rabbit_client(initialized_app: FastAPI) -> RabbitMQClient:
    rabbit_settings: RabbitSettings = initialized_app.state.settings.AGENT_RABBITMQ
    rabbit_client = RabbitMQClient(client_name="testclient", settings=rabbit_settings)

    await rabbit_client.rpc_initialize()

    yield rabbit_client
    rabbit_client.close()


async def _request_volume_removal(
    initialized_app: FastAPI, test_rabbit_client: RabbitMQClient, volumes: list[str]
):
    settings: ApplicationSettings = initialized_app.state.settings

    namespace = RPCNamespace.from_entries(
        {"service": "agent", "docker_node_id": settings.AGENT_DOCKER_NODE_ID}
    )
    await test_rabbit_client.rpc_request(
        namespace,
        "remove_volumes",
        volume_names=volumes,
        volume_removal_attempts=1,
        sleep_between_attempts_s=0.1,
    )


async def test_rpc_remove_volumes_ok(
    initialized_app: FastAPI,
    test_rabbit_client: RabbitMQClient,
    unused_volume: AsyncIterator[DockerVolume],
):
    await _request_volume_removal(
        initialized_app, test_rabbit_client, [unused_volume.name]
    )


async def test_rpc_remove_volumes_volume_does_not_exist(
    initialized_app: FastAPI, test_rabbit_client: RabbitMQClient
):
    missing_volume_name = "volume_does_not_exit"
    with pytest.raises(DockerError, match=f"get {missing_volume_name}: no such volume"):
        await _request_volume_removal(
            initialized_app, test_rabbit_client, [missing_volume_name]
        )
