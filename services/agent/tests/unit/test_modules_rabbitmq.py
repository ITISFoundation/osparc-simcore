# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

import aiodocker
import pytest
from aiodocker.volumes import DockerVolume
from fastapi import FastAPI
from models_library.sidecar_volumes import VolumeCategory, VolumeState
from pytest import LogCaptureFixture
from pytest_mock import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCNamespace
from servicelib.sidecar_volumes import STORE_FILE_NAME
from settings_library.rabbit import RabbitSettings
from simcore_service_agent.core.application import create_app
from simcore_service_agent.core.settings import ApplicationSettings
from simcore_service_agent.modules.models import SidecarVolumes, VolumeDict
from simcore_service_agent.modules.volumes_cleanup import _core
from utils import ParsingModel, create_volume, get_sidecar_volumes, get_volume_states

pytest_simcore_core_services_selection = [
    "rabbit",
]


# UTILS


async def _request_volume_removal(
    initialized_app: FastAPI,
    test_rabbit_client: RabbitMQClient,
    volumes: list[str],
    *,
    timeout: float,
):
    settings: ApplicationSettings = initialized_app.state.settings

    namespace = RPCNamespace.from_entries(
        {
            "service": "agent",
            "docker_node_id": settings.AGENT_DOCKER_NODE_ID,
            "swarm_stack_name": settings.AGENT_VOLUMES_CLEANUP_TARGET_SWARM_STACK_NAME,
        }
    )
    await test_rabbit_client.rpc_request(
        namespace,
        "remove_volumes",
        volume_names=volumes,
        volume_remove_timeout_s=timeout,
        timeout_s_method=timeout,
        timeout_s_connection_error=1,
    )


@asynccontextmanager
async def _create_volumes(count: int, tmp_path: Path) -> AsyncIterator[list[list[str]]]:
    volumes: set[DockerVolume] = set()

    async def _generate_random_volumes(docker_client: aiodocker.Docker) -> list[str]:
        # Generate some volimes that look like the

        sidecar_volumes: SidecarVolumes = get_sidecar_volumes()
        volume_states: dict[VolumeCategory, VolumeState] = get_volume_states(
            sidecar_volumes
        )

        # store the file to be uploaded with the states somewhere
        file_with_data = tmp_path / f"{uuid4()}" / STORE_FILE_NAME
        file_with_data.parent.mkdir(parents=True, exist_ok=True)
        file_with_data.write_text(ParsingModel(volume_states=volume_states).json())

        store_volume_name = sidecar_volumes.store_volume["Name"]
        created_store_volume: VolumeDict = await create_volume(
            store_volume_name,
            volume_path_in_container=Path("/") / STORE_FILE_NAME,
            dir_to_copy=file_with_data,
        )
        volumes.add(DockerVolume(docker_client, created_store_volume["Name"]))

        for volume in sidecar_volumes.remaining_volumes:
            volume_name = volume["Name"]
            created_other_volume: VolumeDict = await create_volume(volume_name)
            volumes.add(DockerVolume(docker_client, created_other_volume["Name"]))

        return [x.name for x in volumes]

    async with aiodocker.Docker() as docker_client:
        yield [await _generate_random_volumes(docker_client) for _ in range(count)]

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
async def test_rabbit_client(initialized_app: FastAPI) -> AsyncIterator[RabbitMQClient]:
    rabbit_settings: RabbitSettings = initialized_app.state.settings.AGENT_RABBITMQ
    rabbit_client = RabbitMQClient(client_name="testclient", settings=rabbit_settings)

    await rabbit_client.rpc_initialize()

    yield rabbit_client
    await rabbit_client.close()


@pytest.fixture
def infinitely_running_volumes_removal_task(mocker: MockerFixture) -> None:
    async def _sleep_forever(*arg: Any, **kwargs: Any) -> None:
        while True:
            print("sleeping Zzzzzzzz")
            await asyncio.sleep(0.1)

    mocker.patch.object(
        _core, "backup_and_remove_sidecar_volumes", side_effect=_sleep_forever
    )
    # __name__ is missing from mock
    # pylint:disable=protected-access
    _core.backup_and_remove_sidecar_volumes.__name__ = _sleep_forever.__name__


# TESTS


async def test_rpc_remove_volumes_ok(
    initialized_app: FastAPI, test_rabbit_client: RabbitMQClient, tmp_path: Path
):
    async with _create_volumes(1, tmp_path) as volumes:
        assert len(volumes) == 1
        await _request_volume_removal(
            initialized_app, test_rabbit_client, volumes[0], timeout=2
        )


async def test_rpc_remove_volumes_in_parallel_ok(
    initialized_app: FastAPI, test_rabbit_client: RabbitMQClient, tmp_path: Path
):
    async with _create_volumes(10, tmp_path) as volumes:
        await asyncio.gather(
            *(
                _request_volume_removal(
                    initialized_app, test_rabbit_client, v, timeout=30
                )
                for v in volumes
            )
        )


async def test_rpc_remove_volumes_with_already_running_volumes_removal_task_ok(
    caplog_debug: LogCaptureFixture,
    infinitely_running_volumes_removal_task: None,
    initialized_app: FastAPI,
    test_rabbit_client: RabbitMQClient,
    tmp_path: Path,
):
    caplog_debug.clear()

    async with _create_volumes(10, tmp_path) as volumes:
        await asyncio.gather(
            *(
                _request_volume_removal(
                    initialized_app, test_rabbit_client, v, timeout=30
                )
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
        aiodocker.DockerError, match=rf"DockerError.*404.*{missing_volume_name}.*"
    ):
        await _request_volume_removal(
            initialized_app, test_rabbit_client, [missing_volume_name], timeout=2
        )
