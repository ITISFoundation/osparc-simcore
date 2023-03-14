# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from uuid import uuid4

import aiodocker
import pytest
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from pytest import LogCaptureFixture
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_errors import GatheredRuntimeErrors
from servicelib.rabbitmq_utils import RPCNamespace
from settings_library.rabbit import RabbitSettings
from simcore_service_agent.core.application import create_app
from simcore_service_agent.core.settings import ApplicationSettings
from simcore_service_agent.modules.volumes_cleanup import _core

pytest_simcore_core_services_selection = [
    "rabbit",
]


# UTILS


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
        timeout_s_method=5,
        timeout_s_connection_error=1,
    )


@asynccontextmanager
async def _create_volumes(count: int) -> list[str]:
    volumes: set[DockerVolume] = set()
    async with aiodocker.Docker() as docker_client:
        result = await asyncio.gather(
            *(
                docker_client.volumes.create({"Name": f"volume-to-remove{uuid4()}"})
                for _ in range(count)
            )
        )
        volumes.update(result)

        yield [x.name for x in volumes]

        try:
            await asyncio.gather(*(v.delete() for v in volumes))
        except aiodocker.DockerError:
            pass


# FIXTURES


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


@pytest.fixture
def infinitely_running_volumes_removal_task(mocker: MockerFixture) -> None:
    async def _sleep_forever(*arg: Any, **kwargs: Any) -> None:
        while True:
            print("sleeping Zzzzzzzz")
            await asyncio.sleep(0.1)

    mocker.patch.object(_core, "_backup_and_remove_volumes", side_effect=_sleep_forever)
    # __name__ is missing from mock
    # pylint:disable=protected-access
    _core._backup_and_remove_volumes.__name__ = _sleep_forever.__name__


# TESTS


async def test_rpc_remove_volumes_ok(
    initialized_app: FastAPI, test_rabbit_client: RabbitMQClient
):
    async with _create_volumes(100) as volumes:
        await _request_volume_removal(initialized_app, test_rabbit_client, volumes)


async def test_rpc_remove_volumes_in_parallel_ok(
    initialized_app: FastAPI, test_rabbit_client: RabbitMQClient
):
    async with _create_volumes(100) as volumes:
        await asyncio.gather(
            *(
                _request_volume_removal(initialized_app, test_rabbit_client, [v])
                for v in volumes
            )
        )


async def test_rpc_remove_volumes_with_already_running_volumes_removal_task_ok(
    caplog_debug: LogCaptureFixture,
    infinitely_running_volumes_removal_task: None,
    initialized_app: FastAPI,
    test_rabbit_client: RabbitMQClient,
):
    caplog_debug.clear()

    async with _create_volumes(100) as volumes:
        await asyncio.gather(
            *(
                _request_volume_removal(initialized_app, test_rabbit_client, [v])
                for v in volumes
            )
        )

    handler_name = "backup_and_remove_volumes"
    assert f"Disabled '{handler_name}' job." in caplog_debug.text
    assert f"Enabled '{handler_name}' job." in caplog_debug.text


async def test_rpc_remove_volumes_volume_does_not_exist(
    initialized_app: FastAPI, test_rabbit_client: RabbitMQClient
):
    missing_volume_name = "volume_does_not_exit"
    with pytest.raises(
        GatheredRuntimeErrors, match=f"get {missing_volume_name}: no such volume"
    ) as exec_info:
        await _request_volume_removal(
            initialized_app, test_rabbit_client, [missing_volume_name]
        )
    assert len(exec_info.value.errors) == 1, f"{exec_info.value.errors}"
