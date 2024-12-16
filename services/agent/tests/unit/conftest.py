# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import aiodocker
import pytest
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.testclient import TestClient
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from settings_library.rabbit import RabbitSettings
from simcore_service_agent.core.application import create_app
from utils import VOLUMES_TO_CREATE, get_source


@pytest.fixture
def service_env(
    monkeypatch: pytest.MonkeyPatch,
    mock_environment: EnvVarsDict,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **mock_environment,
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
        },
    )


@pytest.fixture
async def initialized_app(service_env: EnvVarsDict) -> AsyncIterator[FastAPI]:
    app: FastAPI = create_app()

    async with LifespanManager(app):
        yield app


@pytest.fixture
def test_client(initialized_app: FastAPI) -> TestClient:
    return TestClient(initialized_app)


@pytest.fixture
def service_run_id() -> ServiceRunID:
    return ServiceRunID.create_for_dynamic_sidecar()


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def user_id() -> UserID:
    return 1


@pytest.fixture
def volumes_path(tmp_path: Path) -> Path:
    return tmp_path / "volumes"


@pytest.fixture
async def create_dynamic_sidecar_volume(
    service_run_id: ServiceRunID,
    project_id: ProjectID,
    swarm_stack_name: str,
    user_id: UserID,
    volumes_path: Path,
) -> AsyncIterable[Callable[[NodeID, bool, str], Awaitable[str]]]:
    volumes_to_cleanup: list[DockerVolume] = []
    containers_to_cleanup: list[DockerContainer] = []

    async with aiodocker.Docker() as docker_client:

        async def _(node_id: NodeID, in_use: bool, volume_name: str) -> str:
            source = get_source(service_run_id, node_id, volumes_path / volume_name)
            volume = await docker_client.volumes.create(
                {
                    "Name": source,
                    "Labels": {
                        "node_uuid": f"{node_id}",
                        "run_id": service_run_id,
                        "source": source,
                        "study_id": f"{project_id}",
                        "swarm_stack_name": swarm_stack_name,
                        "user_id": f"{user_id}",
                    },
                }
            )
            volumes_to_cleanup.append(volume)

            if in_use:
                container = await docker_client.containers.run(
                    config={
                        "Cmd": ["/bin/ash", "-c", "sleep 10000"],
                        "Image": "alpine:latest",
                        "HostConfig": {"Binds": [f"{volume.name}:{volumes_path}"]},
                    },
                    name=f"using_volume_{volume.name}",
                )
                await container.start()
                containers_to_cleanup.append(container)

            return source

        yield _

        for container in containers_to_cleanup:
            with suppress(aiodocker.DockerError):
                await container.delete(force=True)
        for volume in volumes_to_cleanup:
            with suppress(aiodocker.DockerError):
                await volume.delete()


@pytest.fixture
def create_dynamic_sidecar_volumes(
    create_dynamic_sidecar_volume: Callable[[NodeID, bool, str], Awaitable[str]]
) -> Callable[[NodeID, bool], Awaitable[set[str]]]:
    async def _(node_id: NodeID, in_use: bool) -> set[str]:
        volume_names: set[str] = set()
        for volume_name in VOLUMES_TO_CREATE:
            name = await create_dynamic_sidecar_volume(node_id, in_use, volume_name)
            volume_names.add(name)

        return volume_names

    return _
