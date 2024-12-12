# pylint: disable=redefined-outer-name


import logging
from collections.abc import AsyncIterable, Awaitable, Callable
from enum import Enum

import pytest
from aiodocker import Docker, DockerError
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_directorv2.services import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from models_library.projects_nodes_io import NodeID
from simcore_service_agent.services.containers_manager import (
    get_containers_manager,
    setup_containers_manager,
)


@pytest.fixture
async def app() -> AsyncIterable[FastAPI]:
    app = FastAPI()
    setup_containers_manager(app)

    async with LifespanManager(app):
        yield app


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
async def docker() -> AsyncIterable[Docker]:
    async with Docker() as docker:
        yield docker


class _ContainerMode(Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"


@pytest.fixture
async def create_container(
    docker: Docker,
) -> AsyncIterable[Callable[[str, _ContainerMode], Awaitable[str]]]:
    created_containers: set[str] = set()

    async def _(name: str, container_mode: _ContainerMode) -> str:
        container = await docker.containers.create(
            config={
                "Image": "alpine",
                "Cmd": ["sh", "-c", "while true; do sleep 1; done"],
            },
            name=name,
        )

        if container_mode in (_ContainerMode.RUNNING, _ContainerMode.STOPPED):
            await container.start()
        if container_mode == _ContainerMode.STOPPED:
            await container.stop()

        created_containers.add(container.id)
        return container.id

    yield _

    # cleanup containers
    for container_id in created_containers:
        try:
            container = await docker.containers.get(container_id)
            await container.delete(force=True)
        except DockerError as e:
            if e.status != status.HTTP_404_NOT_FOUND:
                raise


async def test_force_container_cleanup(
    app: FastAPI,
    node_id: NodeID,
    create_container: Callable[[str, _ContainerMode], Awaitable[str]],
    faker: Faker,
    caplog: pytest.LogCaptureFixture,
):
    caplog.set_level(logging.DEBUG)
    caplog.clear()

    proxy_name = f"{DYNAMIC_PROXY_SERVICE_PREFIX}_{node_id}{faker.pystr()}"
    dynamic_sidecar_name = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}-{node_id}{faker.pystr()}"
    user_service_name = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{node_id}{faker.pystr()}"

    await create_container(proxy_name, _ContainerMode.CREATED)
    await create_container(dynamic_sidecar_name, _ContainerMode.RUNNING)
    await create_container(user_service_name, _ContainerMode.STOPPED)

    await get_containers_manager(app).force_container_cleanup(node_id)

    assert proxy_name in caplog.text
    assert dynamic_sidecar_name in caplog.text
    assert user_service_name in caplog.text
