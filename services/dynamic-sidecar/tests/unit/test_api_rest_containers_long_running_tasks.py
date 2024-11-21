# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=no-member

import json
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager
from inspect import getmembers, isfunction
from pathlib import Path
from typing import Any, Final, NamedTuple
from unittest.mock import AsyncMock

import aiodocker
import faker
import pytest
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi.routing import APIRoute
from httpx import AsyncClient
from models_library.api_schemas_long_running_tasks.base import (
    ProgressMessage,
    ProgressPercent,
)
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pydantic import AnyHttpUrl, TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    TaskClientResultError,
    TaskId,
    periodic_task_result,
)
from servicelib.fastapi.long_running_tasks.client import setup as client_setup
from simcore_sdk.node_ports_common.exceptions import NodeNotFound
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.api.rest import containers_long_running_tasks
from simcore_service_dynamic_sidecar.core.validation import InvalidComposeSpecError
from simcore_service_dynamic_sidecar.models.schemas.containers import (
    ContainersComposeSpec,
    ContainersCreate,
)
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules.inputs import enable_inputs_pulling
from simcore_service_dynamic_sidecar.modules.outputs._context import OutputsContext
from simcore_service_dynamic_sidecar.modules.outputs._manager import OutputsManager

FAST_STATUS_POLL: Final[float] = 0.1
CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60
DEFAULT_COMMAND_TIMEOUT: Final[int] = 5


class ContainerTimes(NamedTuple):
    created: Any
    started_at: Any
    finished_at: Any


# UTILS


def _print_routes(app: FastAPI) -> None:
    endpoints = [route.path for route in app.routes if isinstance(route, APIRoute)]
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
                    "image": "alpine:latest",
                    "networks": {
                        _get_dynamic_sidecar_network_name(): None,
                    },
                },
                "second-box": {
                    "image": "alpine:latest",
                    "command": ["sh", "-c", "sleep 100000"],
                },
            },
            "networks": {_get_dynamic_sidecar_network_name(): None},
        },
        {
            "version": "3",
            "services": {
                "solo-box": {
                    "image": "alpine:latest",
                    "command": ["sh", "-c", "sleep 100000"],
                },
            },
        },
    ]
)
def compose_spec(request: pytest.FixtureRequest) -> str:
    spec_dict: dict[str, Any] = request.param  # type: ignore
    return json.dumps(spec_dict)


@pytest.fixture
def backend_url() -> AnyHttpUrl:
    return TypeAdapter(AnyHttpUrl).validate_python("http://backgroud.testserver.io")


@pytest.fixture
def mock_environment(mock_rabbitmq_envs: EnvVarsDict) -> EnvVarsDict:
    return mock_rabbitmq_envs


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
        base_url=f"{backend_url}",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


@pytest.fixture
def client(
    app: FastAPI, httpx_async_client: AsyncClient, backend_url: AnyHttpUrl
) -> Client:
    return Client(app=app, async_client=httpx_async_client, base_url=f"{backend_url}")


@pytest.fixture
def shared_store(httpx_async_client: AsyncClient) -> SharedStore:
    # pylint: disable=protected-access
    return httpx_async_client._transport.app.state.shared_store  # noqa: SLF001


@pytest.fixture
def mock_data_manager(mocker: MockerFixture) -> None:
    for function_name in (
        "_push_directory",
        "_state_metadata_entry_exists",
        "_pull_directory",
        "_pull_legacy_archive",
    ):
        mocker.patch(
            f"simcore_service_dynamic_sidecar.modules.long_running_tasks.data_manager.{function_name}",
            autospec=True,
            return_value=None,
        )


@pytest.fixture()
def mock_nodeports(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager.upload_outputs",
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
async def mock_port_keys(
    request: pytest.FixtureRequest, client: Client
) -> list[str] | None:
    outputs_context: OutputsContext = client.app.state.outputs_context
    if request.param is not None:
        await outputs_context.set_file_type_port_keys(request.param)
    return request.param


@pytest.fixture
def outputs_manager(client: Client) -> OutputsManager:
    return client.app.state.outputs_manager


@pytest.fixture
def missing_node_uuid(faker: faker.Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def mock_node_missing(mocker: MockerFixture, missing_node_uuid: str) -> None:
    async def _mocked(*args, **kwargs) -> None:
        raise NodeNotFound(missing_node_uuid)

    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.outputs._manager.upload_outputs",
        side_effect=_mocked,
    )


async def _get_task_id_pull_user_servcices_docker_images(
    httpx_async_client: AsyncClient, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(f"/{API_VTAG}/containers/images:pull")
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_create_service_containers(
    httpx_async_client: AsyncClient,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    *args,
    **kwargs,
) -> TaskId:
    containers_compose_spec = ContainersComposeSpec(
        docker_compose_yaml=compose_spec,
    )
    await httpx_async_client.post(
        f"/{API_VTAG}/containers/compose-spec",
        json=containers_compose_spec.model_dump(),
    )
    containers_create = ContainersCreate(metrics_params=mock_metrics_params)
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers", json=containers_create.model_dump()
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
    httpx_async_client: AsyncClient, port_keys: list[str] | None, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/ports/inputs:pull", json=port_keys
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_task_ports_outputs_pull(
    httpx_async_client: AsyncClient, port_keys: list[str] | None, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/ports/outputs:pull", json=port_keys
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_task_ports_outputs_push(
    httpx_async_client: AsyncClient, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers/ports/outputs:push"
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _get_task_id_task_containers_restart(
    httpx_async_client: AsyncClient, command_timeout: int, *args, **kwargs
) -> TaskId:
    response = await httpx_async_client.post(
        f"/{API_VTAG}/containers:restart",
        params={"command_timeout": command_timeout},
    )
    task_id: TaskId = response.json()
    assert isinstance(task_id, str)
    return task_id


async def _debug_progress(
    message: ProgressMessage, percent: ProgressPercent | None, task_id: TaskId
) -> None:
    print(f"{task_id} {percent} {message}")


async def test_create_containers_task(
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
) -> None:
    last_progress_message: tuple[str, float] | None = None

    async def create_progress(message: str, percent: float, _: TaskId) -> None:
        nonlocal last_progress_message
        last_progress_message = (message, percent)
        print(message, percent)

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=create_progress,
    ) as result:
        assert shared_store.container_names == result

    assert last_progress_message == ("finished", 1.0)


async def test_pull_user_servcices_docker_images(
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
) -> None:
    last_progress_message: tuple[ProgressMessage, ProgressPercent] | None = None

    async def create_progress(
        message: ProgressMessage, percent: ProgressPercent | None, _: TaskId
    ) -> None:
        nonlocal last_progress_message
        assert percent is not None
        last_progress_message = (message, percent)
        print(message, percent)

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=create_progress,
    ) as result:
        assert shared_store.container_names == result

    assert last_progress_message == ("finished", 1.0)

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_pull_user_servcices_docker_images(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    ) as result:
        assert result is None
    assert last_progress_message == ("finished", 1.0)


async def test_create_containers_task_invalid_yaml_spec(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
):
    with pytest.raises(InvalidComposeSpecError) as exec_info:
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_create_service_containers(
                httpx_async_client, "", mock_metrics_params
            ),
            task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=FAST_STATUS_POLL,
            progress_callback=_debug_progress,
        ):
            pass
    assert "Provided yaml is not valid" in f"{exec_info.value}"


@pytest.mark.parametrize(
    "get_task_id_callable",
    [
        _get_task_id_pull_user_servcices_docker_images,
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
async def test_same_task_id_is_returned_if_task_exists(
    httpx_async_client: AsyncClient,
    client: Client,
    mocker: MockerFixture,
    get_task_id_callable: Callable[..., Awaitable],
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    compose_spec: str,
) -> None:
    def _get_awaitable() -> Awaitable:
        return get_task_id_callable(
            httpx_async_client=httpx_async_client,
            compose_spec=compose_spec,
            mock_metrics_params=mock_metrics_params,
            port_keys=None,
            command_timeout=0,
        )

    with mock_tasks(mocker):
        task_id = await _get_awaitable()
        async with auto_remove_task(client, task_id):
            assert await _get_awaitable() == task_id

        # since the previous task was already removed it is again possible
        # to create a task
        new_task_id = await _get_awaitable()
        assert new_task_id != task_id
        async with auto_remove_task(client, task_id):
            pass


async def test_containers_down_after_starting(
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
    mock_core_rabbitmq: dict[str, AsyncMock],
    mocker: MockerFixture,
):
    # start containers
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    ) as result:
        assert shared_store.container_names == result

    # put down containers
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_docker_compose_down(httpx_async_client),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    ) as result:
        assert result is None


async def test_containers_down_missing_spec(
    httpx_async_client: AsyncClient,
    client: Client,
    caplog_info_debug: pytest.LogCaptureFixture,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_docker_compose_down(httpx_async_client),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
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
        progress_callback=_debug_progress,
    ) as result:
        assert isinstance(result, int)


async def test_container_save_state(
    httpx_async_client: AsyncClient, client: Client, mock_data_manager: None
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_state_save(httpx_async_client),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    ) as result:
        assert isinstance(result, int)


@pytest.mark.parametrize("inputs_pulling_enabled", [True, False])
async def test_container_pull_input_ports(
    httpx_async_client: AsyncClient,
    client: Client,
    inputs_pulling_enabled: bool,
    app: FastAPI,
    mock_port_keys: list[str] | None,
    mock_nodeports: None,
):
    if inputs_pulling_enabled:
        enable_inputs_pulling(app)

    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_task_ports_inputs_pull(
            httpx_async_client, mock_port_keys
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    ) as result:
        assert result == (42 if inputs_pulling_enabled else 0)


async def test_container_pull_output_ports(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_port_keys: list[str] | None,
    mock_nodeports: None,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_task_ports_outputs_pull(
            httpx_async_client, mock_port_keys
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    ) as result:
        assert result == 42


async def test_container_push_output_ports(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_port_keys: list[str] | None,
    mock_nodeports: None,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_task_ports_outputs_push(
            httpx_async_client, mock_port_keys
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    ) as result:
        assert result is None


async def test_container_push_output_ports_missing_node(
    httpx_async_client: AsyncClient,
    client: Client,
    mock_port_keys: list[str] | None,
    missing_node_uuid: str,
    mock_node_missing: None,
    outputs_manager: OutputsManager,
):
    for port_key in mock_port_keys if mock_port_keys else []:
        await outputs_manager.port_key_content_changed(port_key)

    async def _test_code() -> None:
        async with periodic_task_result(
            client=client,
            task_id=await _get_task_id_task_ports_outputs_push(
                httpx_async_client, mock_port_keys
            ),
            task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=FAST_STATUS_POLL,
            progress_callback=_debug_progress,
        ):
            pass

    if not mock_port_keys:
        await _test_code()
    else:
        with pytest.raises(TaskClientResultError) as exec_info:
            await _test_code()
        assert f"the node id {missing_node_uuid} was not found" in f"{exec_info.value}"


async def test_containers_restart(
    httpx_async_client: AsyncClient,
    client: Client,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
):
    async with periodic_task_result(
        client=client,
        task_id=await _get_task_id_create_service_containers(
            httpx_async_client, compose_spec, mock_metrics_params
        ),
        task_timeout=CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=FAST_STATUS_POLL,
        progress_callback=_debug_progress,
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
        progress_callback=_debug_progress,
    ) as result:
        assert result is None

    container_timestamps_after = await _get_container_timestamps(container_names)

    for container_name in container_names:
        before: ContainerTimes = container_timestamps_before[container_name]
        after: ContainerTimes = container_timestamps_after[container_name]

        assert before.created == after.created
        assert before.started_at < after.started_at
        assert before.finished_at < after.finished_at
