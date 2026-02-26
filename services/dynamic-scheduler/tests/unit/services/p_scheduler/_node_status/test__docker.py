# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import AsyncIterable, Awaitable, Callable
from typing import Final
from unittest.mock import MagicMock

import pytest
import pytest_mock
from aiodocker import Docker, DockerError
from faker import Faker
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from settings_library.redis import RedisSettings
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._docker import (
    _PREFIX_DY_PROXY,
    _PREFIX_DY_SIDECAR,
    get_service_category,
    is_service_running,
)
from simcore_service_dynamic_scheduler.services.p_scheduler._node_status._models import ServiceCategory, ServiceName
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

_RETRY_PARAMS: Final[dict] = {
    "stop": stop_after_delay(20),
    "wait": wait_fixed(0.1),
    "retry": retry_if_exception_type(AssertionError),
    "reraise": True,
}


@pytest.fixture
def app_environment(
    disable_generic_scheduler_lifespan: None,
    disable_postgres_lifespan: None,
    disable_rabbitmq_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    disable_p_scheduler_lifespan: None,
    use_in_memory_redis: RedisSettings,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def node_id_legacy(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_new_style_one_of_two(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def node_id_new_style_two_of_two(faker: Faker) -> NodeID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def mocked_minimal_service_data(
    node_id_legacy: NodeID, node_id_new_style_one_of_two: NodeID, node_id_new_style_two_of_two: NodeID
) -> dict[NodeID, list[dict]]:
    return {
        node_id_legacy: [
            {
                "Spec": {
                    "Name": f"random_{node_id_legacy}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_legacy}"},
                }
            },
        ],
        node_id_new_style_one_of_two: [
            {
                "Spec": {
                    "Name": f"{_PREFIX_DY_SIDECAR}_{node_id_new_style_one_of_two}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_new_style_one_of_two}"},
                }
            },
        ],
        node_id_new_style_two_of_two: [
            {
                "Spec": {
                    "Name": f"{_PREFIX_DY_SIDECAR}_{node_id_new_style_two_of_two}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_new_style_two_of_two}"},
                }
            },
            {
                "Spec": {
                    "Name": f"{_PREFIX_DY_PROXY}_{node_id_new_style_two_of_two}",
                    "Labels": {"io.simcore.runtime.node-id": f"{node_id_new_style_two_of_two}"},
                }
            },
        ],
    }


@pytest.fixture
async def mock_service_list(
    mocker: pytest_mock.MockerFixture,
    mocked_minimal_service_data: dict[NodeID, list[dict]],
) -> MagicMock:
    mock_docker = MagicMock()
    all_services = [service for services in mocked_minimal_service_data.values() for service in services]

    async def _filter_services(*, filters: dict | None = None) -> list[dict]:
        if filters is None:
            return all_services
        label_filter = filters.get("label", "")
        # parse "io.simcore.runtime.node-id=<uuid>" format
        if "=" in label_filter:
            _key, value = label_filter.split("=", 1)
            return [s for s in all_services if s.get("Spec", {}).get("Labels", {}).get(_key) == value]
        return all_services

    mock_docker.services.list = _filter_services
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.p_scheduler._node_status._docker.get_remote_docker_client",
        return_value=mock_docker,
    )
    return mock_docker


async def test_get_service_category(
    mock_service_list: None,
    app: FastAPI,
    node_id_legacy: NodeID,
    node_id_new_style_one_of_two: NodeID,
    node_id_new_style_two_of_two: NodeID,
):
    assert await get_service_category(app, node_id_legacy) == {
        ServiceCategory.LEGACY: f"random_{node_id_legacy}",
    }
    assert await get_service_category(app, node_id_new_style_one_of_two) == {
        ServiceCategory.DY_SIDECAR: f"{_PREFIX_DY_SIDECAR}_{node_id_new_style_one_of_two}"
    }
    assert await get_service_category(app, node_id_new_style_two_of_two) == {
        ServiceCategory.DY_SIDECAR: f"{_PREFIX_DY_SIDECAR}_{node_id_new_style_two_of_two}",
        ServiceCategory.DY_PROXY: f"{_PREFIX_DY_PROXY}_{node_id_new_style_two_of_two}",
    }


# now test the
@pytest.fixture
async def mock_get_remote_docker_client(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_scheduler.services.p_scheduler._node_status._docker.get_remote_docker_client",
        return_value=Docker(),
    )


async def test_is_service_running_missing_service(
    docker_swarm: None, mock_get_remote_docker_client: None, app: FastAPI
):
    assert await is_service_running(app, "missing_service") is False


@pytest.fixture
async def aiodocker_client(docker_swarm: None) -> AsyncIterable[Docker]:
    async with Docker() as docker:
        yield docker


@pytest.fixture
async def create_service(aiodocker_client: Docker) -> AsyncIterable[Callable[[ServiceName], Awaitable[None]]]:
    started_services: set[ServiceName] = set()

    async def _(service_name: ServiceName) -> None:
        service = await aiodocker_client.services.create(
            task_template={"ContainerSpec": {"Image": "busybox:latest", "Command": ["sleep", "300"]}},
            name=service_name,
        )
        assert service
        started_services.add(service_name)

    yield _

    for service_name in started_services:
        try:
            await aiodocker_client.services.delete(service_name)
        except DockerError as e:
            if e.status != status.HTTP_404_NOT_FOUND:
                raise


async def test_is_service_running(
    mock_get_remote_docker_client: None,
    aiodocker_client: Docker,
    app: FastAPI,
    create_service: Callable[[ServiceName], Awaitable[None]],
):
    service_name = "test_service"
    await create_service(service_name)

    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            print("CHECK IS RUNNING")
            assert await is_service_running(app, service_name) is True

    # stop the service by removing it
    await aiodocker_client.services.delete(service_name)

    # wait for the service to be gone
    async for attempt in AsyncRetrying(**_RETRY_PARAMS):
        with attempt:
            print("CHECK IS NOT")
            assert await is_service_running(app, service_name) is False
