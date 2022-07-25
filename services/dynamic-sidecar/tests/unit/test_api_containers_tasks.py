# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterable, AsyncIterator, Final, Iterator, Optional

import pytest
from _pytest.fixtures import FixtureRequest
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import AsyncClient
from pydantic import AnyHttpUrl, parse_obj_as
from pytest_mock.plugin import MockerFixture
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    TaskClientResultError,
    TaskId,
    periodic_task_result,
)
from servicelib.fastapi.long_running_tasks.client import setup as client_setup
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.api import containers_tasks
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore

FAST_STATUS_POLL: Final[float] = 0.1
CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60

# UTILS


def __print_routes(app: FastAPI) -> None:
    endpoints = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoints.append(route.path)

    print("ROUTES\n", json.dumps(endpoints, indent=2))


def _get_dynamic_sidecar_network_name() -> str:
    return "entrypoint_container_network"


@contextmanager
def mock_task(*, task_name: str) -> Iterator[None]:
    # NOTE: mocking via `mocker: MockerFixture` appears not to works
    async def _long_running_task(*args, **kwargs) -> None:
        print(f"Called mocked function with {args}, {kwargs}")

    original_task = getattr(containers_tasks, task_name)

    setattr(containers_tasks, task_name, _long_running_task)

    yield

    setattr(containers_tasks, task_name, original_task)


@asynccontextmanager
async def auto_remove_task(client: Client, task_id: TaskId) -> AsyncIterator[None]:
    """clenup pending tasks"""
    try:
        yield
    finally:
        await client.cancel_and_delete_task(task_id, timeout=10)


# FIXTURES


@pytest.fixture
def dynamic_sidecar_network_name() -> str:
    return _get_dynamic_sidecar_network_name()


@pytest.fixture(
    params=[
        {
            "version": "3",
            "services": {
                "first-box": {
                    "image": "busybox",
                    "networks": [
                        _get_dynamic_sidecar_network_name(),
                    ],
                },
                "second-box": {"image": "busybox"},
            },
            "networks": {_get_dynamic_sidecar_network_name(): {}},
        },
        {
            "version": "3",
            "services": {
                "solo-box": {"image": "busybox"},
            },
        },
    ]
)
def compose_spec(request: FixtureRequest) -> str:
    spec_dict: dict[str, Any] = request.param  # type: ignore
    return json.dumps(spec_dict)


@pytest.fixture
def backend_url() -> AnyHttpUrl:
    return parse_obj_as(AnyHttpUrl, "http://backgroud.testserver.io")


@pytest.fixture
async def app(app: FastAPI) -> AsyncIterable[FastAPI]:
    # add the client setup to the same application
    # this is only required for testing, in reality
    # this will be in a different process
    client_setup(app)
    async with LifespanManager(app):
        __print_routes(app)
        yield app


@pytest.fixture
async def httpx_async_client(
    app: FastAPI,
    backend_url: AnyHttpUrl,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers: None,
) -> AsyncIterable[AsyncClient]:
    async with AsyncClient(
        app=app,
        base_url=backend_url,
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def client(
    app: FastAPI, httpx_async_client: AsyncClient, backend_url: AnyHttpUrl
) -> Client:
    return Client(app=app, async_client=httpx_async_client, base_url=backend_url)


@pytest.fixture
def shared_store(httpx_async_client: AsyncClient) -> SharedStore:
    # pylint: disable=protected-access
    return httpx_async_client._transport.app.state.shared_store


@pytest.fixture
def mock_data_manager(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.api.containers_extension.data_manager.push",
        autospec=True,
        return_value=None,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.api.containers_extension.data_manager.exists",
        autospec=True,
        return_value=True,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.api.containers_extension.data_manager.pull",
        autospec=True,
        return_value=None,
    )


# TESTS


async def _get_task_id_create_service_containers(
    httpx_async_client: AsyncClient, compose_spec: str
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/tasks", json={"docker_compose_yaml": compose_spec}
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_docker_compose_down(httpx_async_client: AsyncClient) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers/tasks:down")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_state_restore(httpx_async_client: AsyncClient) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/tasks/state:restore"
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_state_save(httpx_async_client: AsyncClient) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers/tasks/state:save")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def test_create_containers_task(
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    shared_store: SharedStore,
) -> None:
    last_progress_message: Optional[tuple[str, float]] = None

    async def create_progress(message: str, percent: float) -> None:
        nonlocal last_progress_message
        last_progress_message = (message, percent)
        print(message, percent)

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=create_progress,
    ) as result:
        assert shared_store.container_names == result

    assert last_progress_message == ("done", 1)


async def test_create_containers_task_invalid_yaml_spec(
    httpx_async_client: AsyncClient, client: Client
):
    with pytest.raises(TaskClientResultError) as exec_info:
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_create_service_containers(
                httpx_async_client, ""
            ),
            task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=FAST_STATUS_POLL,
        ):
            pass
    assert "raise InvalidComposeSpec" in f"{exec_info.value}"


async def test_create_containers_task_unique(
    httpx_async_client: AsyncClient, client: Client
) -> None:
    with mock_task(task_name="_task_create_service_containers"):
        task_id = await _get_task_id_create_service_containers(httpx_async_client, "")
        async with auto_remove_task(client, task_id):

            # cannot create a task while another unique task is running
            with pytest.raises(AssertionError) as exec_info:
                await _get_task_id_create_service_containers(httpx_async_client, "")

            assert "must be unique, found:" in f"{exec_info.value}"

        # since the previous task was already removed it is again possible
        # to create a task
        task_id = await _get_task_id_create_service_containers(httpx_async_client, "")
        async with auto_remove_task(client, task_id):
            pass


async def test_containers_down_after_starting(
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    shared_store: SharedStore,
):
    # start containers
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert shared_store.container_names == result

    # put down containers
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_docker_compose_down(httpx_async_client),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result is None


async def test_containers_down_missing_spec(
    httpx_async_client: AsyncClient, client: Client
):
    with pytest.raises(TaskClientResultError) as exec_info:
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_docker_compose_down(httpx_async_client),
            task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=FAST_STATUS_POLL,
        ) as result:
            assert result is None
    assert 'RuntimeError("No compose-spec was found")' in f"{exec_info.value}"


async def test_container_restore_state(
    httpx_async_client: AsyncClient, client: Client, mock_data_manager: None
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_state_restore(httpx_async_client),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result is None


async def test_container_save_state(
    httpx_async_client: AsyncClient, client: Client, mock_data_manager: None
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_state_save(httpx_async_client),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result is None
