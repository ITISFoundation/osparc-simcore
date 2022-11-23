# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from collections import namedtuple
from contextlib import asynccontextmanager, contextmanager
from inspect import getmembers, isfunction
from pathlib import Path
from typing import (
    Any,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    Callable,
    Final,
    Iterator,
    Optional,
)

import aiodocker
import faker
import pytest
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import AsyncClient
from pydantic import AnyHttpUrl, parse_obj_as
from pytest import FixtureRequest, LogCaptureFixture
from pytest_mock.plugin import MockerFixture
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    TaskClientResultError,
    TaskId,
    periodic_task_result,
)
from servicelib.fastapi.long_running_tasks.client import setup as client_setup
from simcore_sdk.node_ports_common.exceptions import NodeNotFound
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.api import containers_long_running_tasks
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore

FAST_STATUS_POLL: Final[float] = 0.1
CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60
DEFAULT_COMMAND_TIMEOUT: Final[int] = 5

ContainerTimes = namedtuple("ContainerTimes", "created, started_at, finished_at")


# UTILS


def _print_routes(app: FastAPI) -> None:
    endpoints = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            endpoints.append(route.path)

    print("ROUTES\n", json.dumps(endpoints, indent=2))


def _get_dynamic_sidecar_network_name() -> str:
    return "entrypoint_container_network"


@contextmanager
def mock_tasks(mocker: MockerFixture) -> Iterator[None]:
    async def _just_log_task(*args, **kwargs) -> None:
        print(f"Called mocked function with {args}, {kwargs}")

    # searching by name since all start with _task
    tasks_names = [
        x[0]
        for x in getmembers(containers_long_running_tasks, isfunction)
        if x[0].startswith("task")
    ]

    for task_name in tasks_names:
        mocker.patch.object(
            containers_long_running_tasks, task_name, new=_just_log_task
        )

    yield None


@asynccontextmanager
async def auto_remove_task(client: Client, task_id: TaskId) -> AsyncIterator[None]:
    """clenup pending tasks"""
    try:
        yield
    finally:
        await client.cancel_and_delete_task(task_id, timeout=10)


async def _get_container_timestamps(
    container_names: list[str],
) -> dict[str, ContainerTimes]:
    container_timestamps: dict[str, ContainerTimes] = {}
    async with aiodocker.Docker() as client:
        for container_name in container_names:
            container: DockerContainer = await client.containers.get(container_name)
            container_inspect: dict[str, Any] = await container.show()
            container_timestamps[container_name] = ContainerTimes(
                created=container_inspect["Created"],
                started_at=container_inspect["State"]["StartedAt"],
                finished_at=container_inspect["State"]["FinishedAt"],
            )

    return container_timestamps


@pytest.fixture
def dynamic_sidecar_network_name() -> str:
    return _get_dynamic_sidecar_network_name()


@pytest.fixture(
    params=[
        {
            "version": "3",
            "services": {
                "first-box": {
                    "image": "busybox:latest",
                    "networks": [
                        _get_dynamic_sidecar_network_name(),
                    ],
                },
                "second-box": {"image": "busybox:latest"},
            },
            "networks": {_get_dynamic_sidecar_network_name(): {}},
        },
        {
            "version": "3",
            "services": {
                "solo-box": {"image": "busybox:latest"},
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
        _print_routes(app)
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
        "simcore_service_dynamic_sidecar.modules.long_running_tasks.data_manager.push",
        autospec=True,
        return_value=None,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.long_running_tasks.data_manager.exists",
        autospec=True,
        return_value=True,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.long_running_tasks.data_manager.pull",
        autospec=True,
        return_value=None,
    )


@pytest.fixture()
def mock_nodeports(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.nodeports.upload_outputs",
        return_value=None,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.nodeports.download_target_ports",
        return_value=42,
    )


@pytest.fixture(
    params=[
        [],
        None,
        ["single_port"],
        ["first_port", "second_port"],
    ]
)
def mock_port_keys(request: FixtureRequest) -> list[str]:
    return request.param


@pytest.fixture
def missing_node_uuid(faker: faker.Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def mock_node_missing(mocker: MockerFixture, missing_node_uuid: str) -> None:
    async def _mocked(*args, **kwargs) -> None:
        raise NodeNotFound(missing_node_uuid)

    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.nodeports.upload_outputs",
        side_effect=_mocked,
    )


async def _get_task_id_create_service_containers(
    httpx_async_client: AsyncClient, compose_spec: str, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": compose_spec}
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_docker_compose_down(
    httpx_async_client: AsyncClient, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers:down")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_state_restore(
    httpx_async_client: AsyncClient, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers/state:restore")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_state_save(
    httpx_async_client: AsyncClient, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers/state:save")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_task_ports_inputs_pull(
    httpx_async_client: AsyncClient, port_keys: list[str], *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/ports/inputs:pull", json=port_keys
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_task_ports_outputs_pull(
    httpx_async_client: AsyncClient, port_keys: list[str], *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/ports/outputs:pull", json=port_keys
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_task_ports_outputs_push(
    httpx_async_client: AsyncClient, port_keys: list[str], *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/ports/outputs:push", json=port_keys
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_task_containers_restart(
    httpx_async_client: AsyncClient, command_timeout: int, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers:restart",
        params=dict(command_timeout=command_timeout),
    )
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

    async def create_progress(message: str, percent: float, _: TaskId) -> None:
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

    assert last_progress_message == ("finished", 1.0)


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


@pytest.mark.parametrize(
    "get_task_id_callable",
    [
        _get_task_id_create_service_containers,
        _get_task_id_docker_compose_down,
        _get_task_id_state_restore,
        _get_task_id_state_save,
        _get_task_id_task_ports_inputs_pull,
        _get_task_id_task_ports_outputs_pull,
        _get_task_id_task_ports_outputs_push,
        _get_task_id_task_containers_restart,
    ],
)
async def test_task_is_unique(
    httpx_async_client: AsyncClient,
    client: Client,
    mocker: MockerFixture,
    get_task_id_callable: Callable[..., Awaitable],
) -> None:
    def _get_awaitable() -> Awaitable:
        return get_task_id_callable(
            httpx_async_client=httpx_async_client,
            compose_spec="",
            port_keys=None,
            command_timeout=0,
        )

    with mock_tasks(mocker):
        task_id = await _get_awaitable()
        async with auto_remove_task(client, task_id):

            # cannot create a task while another unique task is running
            with pytest.raises(AssertionError) as exec_info:
                await _get_awaitable()

            assert "must be unique, found:" in f"{exec_info.value}"

        # since the previous task was already removed it is again possible
        # to create a task
        task_id = await _get_awaitable()
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
    httpx_async_client: AsyncClient,
    client: Client,
    caplog_info_debug: LogCaptureFixture,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_docker_compose_down(httpx_async_client),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result is None
    assert "No compose-spec was found" in caplog_info_debug.text


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


async def test_container_pull_input_ports(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_port_keys: list[str],
    mock_nodeports: None,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_task_ports_inputs_pull(
            httpx_async_client, mock_port_keys
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result == 42


async def test_container_pull_output_ports(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_port_keys: list[str],
    mock_nodeports: None,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_task_ports_outputs_pull(
            httpx_async_client, mock_port_keys
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result == 42


async def test_container_push_output_ports(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_port_keys: list[str],
    mock_nodeports: None,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_task_ports_outputs_push(
            httpx_async_client, mock_port_keys
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result is None


async def test_container_push_output_ports_missing_node(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_port_keys: list[str],
    missing_node_uuid: str,
    mock_node_missing: None,
):
    with pytest.raises(TaskClientResultError) as exec_info:
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_task_ports_outputs_push(
                httpx_async_client, mock_port_keys
            ),
            task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=FAST_STATUS_POLL,
        ):
            pass
    assert f"the node id {missing_node_uuid} was not found" in f"{exec_info.value}"


async def test_containers_restart(
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    shared_store: SharedStore,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as container_names:
        assert shared_store.container_names == container_names

    assert container_names

    container_timestamps_before = await _get_container_timestamps(container_names)

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_task_containers_restart(
            httpx_async_client, DEFAULT_COMMAND_TIMEOUT
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
    ) as result:
        assert result is None

    container_timestamps_after = await _get_container_timestamps(container_names)

    for container_name in container_names:
        before: ContainerTimes = container_timestamps_before[container_name]
        after: ContainerTimes = container_timestamps_after[container_name]

        assert before.created == after.created
        assert before.started_at < after.started_at
        assert before.finished_at < after.finished_at
