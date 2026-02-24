# pylint: disable=no-member
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument

import asyncio
import json
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any, Final, NamedTuple
from unittest.mock import AsyncMock

import aiodocker
import faker
import pytest
import sqlalchemy as sa
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from common_library.serialization import model_dump_with_secrets
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import (
    ContainersComposeSpec,
    ContainersCreate,
)
from models_library.api_schemas_dynamic_sidecar.containers import DockerComposeYamlStr
from models_library.api_schemas_long_running_tasks.base import (
    ProgressMessage,
    ProgressPercent,
)
from models_library.projects_nodes_io import NodeID
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.long_running_tasks import (
    assert_task_is_no_longer_present,
    get_fastapi_long_running_manager,
)
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.fastapi.long_running_tasks._manager import FastAPILongRunningManager
from servicelib.long_running_tasks import lrt_api
from servicelib.long_running_tasks.models import LRTNamespace, TaskId
from servicelib.long_running_tasks.task import TaskRegistry
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import (
    containers,
    containers_long_running_tasks,
)
from settings_library.rabbit import RabbitSettings
from simcore_sdk.node_ports_common.exceptions import NodeNotFound
from simcore_service_dynamic_sidecar.core.validation import InvalidComposeSpecError
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules import long_running_tasks as sidecar_lrts
from simcore_service_dynamic_sidecar.modules.inputs import enable_inputs_pulling
from simcore_service_dynamic_sidecar.modules.outputs._context import OutputsContext
from simcore_service_dynamic_sidecar.modules.outputs._manager import (
    OutputsManager,
    UploadPortsFailedError,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)
from utils import get_lrt_result

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]

_FAST_STATUS_POLL: Final[float] = 0.1
_CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60


class ContainerTimes(NamedTuple):
    created: Any
    started_at: Any
    finished_at: Any


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
def mock_sidecar_lrts(mocker: MockerFixture) -> Iterator[None]:
    async def _just_log_task(*args, **kwargs) -> None:
        print(f"Called mocked function with {args}, {kwargs}")

    TaskRegistry.register(_just_log_task)

    for task_name in [
        sidecar_lrts.pull_user_services_images.__name__,
        sidecar_lrts.create_user_services.__name__,
        sidecar_lrts.remove_user_services.__name__,
        sidecar_lrts.restore_user_services_state_paths.__name__,
        sidecar_lrts.save_user_services_state_paths.__name__,
        sidecar_lrts.pull_user_services_input_ports.__name__,
        sidecar_lrts.pull_user_services_output_ports.__name__,
        sidecar_lrts.push_user_services_output_ports.__name__,
        sidecar_lrts.restart_user_services.__name__,
    ]:
        mocker.patch.object(sidecar_lrts, task_name, new=_just_log_task)

    yield None

    TaskRegistry.unregister(_just_log_task)


@pytest.fixture
def dynamic_sidecar_network_name() -> str:
    return "entrypoint_container_network"


@pytest.fixture(
    params=[
        {
            "version": "3",
            "services": {
                "first-box": {
                    "image": "alpine:latest",
                    "networks": {
                        "entrypoint_container_network": None,
                    },
                },
                "second-box": {
                    "image": "alpine:latest",
                    "command": ["sh", "-c", "sleep 100000"],
                },
            },
            "networks": {"entrypoint_container_network": None},
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
def compose_spec(request: pytest.FixtureRequest) -> DockerComposeYamlStr:
    spec_dict: dict[str, Any] = request.param  # type: ignore
    return json.dumps(spec_dict)


@pytest.fixture
def mock_environment(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db: sa.engine.Engine,
    postgres_env_vars_dict: EnvVarsDict,
    rabbit_service: RabbitSettings,
    mock_environment: EnvVarsDict,
    simcore_services_ready: None,
) -> EnvVarsDict:
    envs = {
        **mock_environment,
        "RABBIT_SETTINGS": json.dumps(model_dump_with_secrets(rabbit_service, show_secrets=True)),
        **postgres_env_vars_dict,
    }
    setenvs_from_dict(monkeypatch, envs)
    return envs


@pytest.fixture
async def rpc_client(
    rpc_client: RabbitMQRPCClient,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers: None,
    ensure_shared_store_dir: Path,
) -> RabbitMQRPCClient:
    # crete dir here
    return rpc_client


@pytest.fixture
def lrt_namespace(app: FastAPI) -> LRTNamespace:
    long_running_manager: FastAPILongRunningManager = app.state.long_running_manager
    return long_running_manager.lrt_namespace


@pytest.fixture
def shared_store(app: FastAPI) -> SharedStore:
    return app.state.shared_store


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
async def mock_port_keys(request: pytest.FixtureRequest, app: FastAPI) -> list[str] | None:
    outputs_context: OutputsContext = app.state.outputs_context
    if request.param is not None:
        await outputs_context.set_file_type_port_keys(request.param)
    return request.param


@pytest.fixture
def outputs_manager(app: FastAPI) -> OutputsManager:
    return app.state.outputs_manager


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


async def _get_task_id_pull_user_services_docker_images_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.pull_user_services_images(
        rpc_client, node_id=node_id, lrt_namespace=lrt_namespace
    )


async def _get_task_id_create_service_containers_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    compose_spec: DockerComposeYamlStr,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    *args,
    **kwargs,
) -> TaskId:
    containers_compose_spec = ContainersComposeSpec(
        docker_compose_yaml=compose_spec,
    )
    await containers.create_compose_spec(rpc_client, node_id=node_id, containers_compose_spec=containers_compose_spec)
    containers_create = ContainersCreate(metrics_params=mock_metrics_params)
    return await containers_long_running_tasks.create_user_services(
        rpc_client,
        node_id=node_id,
        lrt_namespace=lrt_namespace,
        containers_create=containers_create,
    )


async def _get_task_id_runs_docker_compose_down_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.remove_user_services(
        rpc_client, node_id=node_id, lrt_namespace=lrt_namespace
    )


async def _get_task_id_state_restore_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.restore_user_services_state_paths(
        rpc_client, node_id=node_id, lrt_namespace=lrt_namespace
    )


async def _get_task_id_state_save_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.save_user_services_state_paths(
        rpc_client, node_id=node_id, lrt_namespace=lrt_namespace
    )


async def _get_task_id_ports_inputs_pull_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.pull_user_services_input_ports(
        rpc_client, node_id=node_id, lrt_namespace=lrt_namespace, port_keys=port_keys
    )


async def _get_task_id_ports_outputs_pull_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    port_keys: list[str] | None,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.pull_user_services_output_ports(
        rpc_client, node_id=node_id, lrt_namespace=lrt_namespace, port_keys=port_keys
    )


async def _get_task_id_ports_outputs_push_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.push_user_services_output_ports(
        rpc_client, node_id=node_id, lrt_namespace=lrt_namespace
    )


async def _get_task_id_task_containers_restart_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    *args,
    **kwargs,
) -> TaskId:
    return await containers_long_running_tasks.restart_user_services(
        rpc_client,
        node_id=node_id,
        lrt_namespace=lrt_namespace,
    )


async def _debug_progress(message: ProgressMessage, percent: ProgressPercent | None, task_id: TaskId) -> None:
    print(f"{task_id} {percent} {message}")


class _LastProgressMessageTracker:
    def __init__(self) -> None:
        self.last_progress_message: tuple[ProgressMessage, ProgressPercent] | None = None

    async def __call__(self, message: ProgressMessage, percent: ProgressPercent | None, _: TaskId) -> None:
        assert percent is not None
        self.last_progress_message = (message, percent)
        print(message, percent)

    async def assert_progress_finished(self) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_delay(10),
            wait=wait_fixed(0.1),
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
        ):
            with attempt:
                await asyncio.sleep(0)  # yield control to the event loop
                assert self.last_progress_message == ("finished", 1.0)


async def test_create_containers_task(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
) -> None:
    last_progress_message_tracker = _LastProgressMessageTracker()

    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_create_service_containers_task(
            rpc_client, node_id, lrt_namespace, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=last_progress_message_tracker,
    )
    assert shared_store.container_names == result

    await last_progress_message_tracker.assert_progress_finished()


async def test_pull_user_servcices_docker_images(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
) -> None:
    last_progress_message_tracker1 = _LastProgressMessageTracker()

    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_create_service_containers_task(
            rpc_client, node_id, lrt_namespace, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=last_progress_message_tracker1,
    )
    assert shared_store.container_names == result

    await last_progress_message_tracker1.assert_progress_finished()

    last_progress_message_tracker2 = _LastProgressMessageTracker()
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_pull_user_services_docker_images_task(
            rpc_client, node_id, lrt_namespace, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=last_progress_message_tracker2,
    )
    assert result is None
    await last_progress_message_tracker2.assert_progress_finished()


async def test_create_containers_task_invalid_yaml_spec(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
):
    with pytest.raises(InvalidComposeSpecError) as exec_info:
        await get_lrt_result(
            rpc_client,
            lrt_namespace,
            task_id=await _get_task_id_create_service_containers_task(
                rpc_client, node_id, lrt_namespace, "", mock_metrics_params
            ),
            task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=_FAST_STATUS_POLL,
            progress_callback=_debug_progress,
        )
    assert "Provided yaml is not valid" in f"{exec_info.value}"


@pytest.mark.parametrize(
    "get_task_id_callable, endswith",
    [
        (_get_task_id_pull_user_services_docker_images_task, "unique_"),
        (_get_task_id_create_service_containers_task, "unique_"),
        (_get_task_id_runs_docker_compose_down_task, "unique_"),
        (_get_task_id_state_restore_task, "unique_"),
        (_get_task_id_state_save_task, "unique_"),
        (
            _get_task_id_ports_inputs_pull_task,
            "unique_efc820338c0950e8a546297f3ad5ba4cdf403853a3e62c8e79ed47e475c4b1b9",
        ),
        (_get_task_id_ports_outputs_pull_task, "unique_"),
        (_get_task_id_ports_outputs_push_task, "unique_"),
        (_get_task_id_task_containers_restart_task, "unique_"),
    ],
)
async def test_same_task_id_is_returned_if_task_exists(
    mock_sidecar_lrts: None,
    rpc_client: RabbitMQRPCClient,
    app: FastAPI,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    mocker: MockerFixture,
    get_task_id_callable: Callable[..., Awaitable[TaskId]],
    endswith: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    compose_spec: str,
) -> None:
    def _get_awaitable() -> Awaitable[TaskId]:
        return get_task_id_callable(
            rpc_client=rpc_client,
            node_id=node_id,
            lrt_namespace=lrt_namespace,
            compose_spec=compose_spec,
            mock_metrics_params=mock_metrics_params,
            port_keys=None,
        )

    async def _assert_task_removed(task_id: TaskId) -> None:
        await lrt_api.remove_task(rpc_client, lrt_namespace, {}, task_id)
        await assert_task_is_no_longer_present(get_fastapi_long_running_manager(app), task_id, {})

    task_id = await _get_awaitable()
    assert task_id.endswith(endswith)
    assert await _get_awaitable() == task_id

    await _assert_task_removed(task_id)

    # since the previous task was already removed it is again possible
    # to create a task and it will share the same task_id
    new_task_id = await _get_awaitable()
    assert new_task_id.endswith(endswith)
    assert new_task_id == task_id

    await _assert_task_removed(task_id)


async def test_containers_down_after_starting(
    mock_ensure_read_permissions_on_user_service_data: None,
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
    mock_core_rabbitmq: dict[str, AsyncMock],
    mocker: MockerFixture,
):
    # start containers
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_create_service_containers_task(
            rpc_client, node_id, lrt_namespace, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert shared_store.container_names == result

    # put down containers
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_runs_docker_compose_down_task(rpc_client, node_id, lrt_namespace),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert result is None


async def test_containers_down_missing_spec(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    caplog_info_debug: pytest.LogCaptureFixture,
):
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_runs_docker_compose_down_task(rpc_client, node_id, lrt_namespace),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert result is None
    assert "No compose-spec was found" in caplog_info_debug.text


async def test_container_restore_state(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    mock_data_manager: None,
):
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_state_restore_task(rpc_client, node_id, lrt_namespace),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert isinstance(result, int)


async def test_container_save_state(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    mock_data_manager: None,
):
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_state_save_task(rpc_client, node_id, lrt_namespace),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert isinstance(result, int)


@pytest.mark.parametrize("inputs_pulling_enabled", [True, False])
async def test_container_pull_input_ports(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    inputs_pulling_enabled: bool,
    app: FastAPI,
    mock_port_keys: list[str] | None,
    mock_nodeports: None,
):
    if inputs_pulling_enabled:
        enable_inputs_pulling(app)

    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_ports_inputs_pull_task(rpc_client, node_id, lrt_namespace, mock_port_keys),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert result == (42 if inputs_pulling_enabled else 0)


async def test_container_pull_output_ports(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    mock_port_keys: list[str] | None,
    mock_nodeports: None,
):
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_ports_outputs_pull_task(rpc_client, node_id, lrt_namespace, mock_port_keys),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert result == 42


async def test_container_push_output_ports(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    mock_port_keys: list[str] | None,
    mock_nodeports: None,
):
    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_ports_outputs_push_task(rpc_client, node_id, lrt_namespace, mock_port_keys),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert result is None


async def test_container_push_output_ports_missing_node(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    mock_port_keys: list[str] | None,
    missing_node_uuid: str,
    mock_node_missing: None,
    outputs_manager: OutputsManager,
):
    for port_key in mock_port_keys if mock_port_keys else []:
        await outputs_manager.port_key_content_changed(port_key)

    async def _test_code() -> None:
        await get_lrt_result(
            rpc_client,
            lrt_namespace,
            task_id=await _get_task_id_ports_outputs_push_task(rpc_client, node_id, lrt_namespace, mock_port_keys),
            task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
            status_poll_interval=_FAST_STATUS_POLL,
            progress_callback=_debug_progress,
        )

    if not mock_port_keys:
        await _test_code()
    else:
        with pytest.raises(UploadPortsFailedError) as exec_info:
            await _test_code()
        assert f"the node id {missing_node_uuid} was not found" in f"{exec_info.value}"


async def test_containers_restart(
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    compose_spec: str,
    mock_stop_heart_beat_task: AsyncMock,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
    shared_store: SharedStore,
):
    container_names = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_create_service_containers_task(
            rpc_client, node_id, lrt_namespace, compose_spec, mock_metrics_params
        ),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert shared_store.container_names == container_names

    assert container_names

    container_timestamps_before = await _get_container_timestamps(container_names)

    result = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id=await _get_task_id_task_containers_restart_task(rpc_client, node_id, lrt_namespace),
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
        status_poll_interval=_FAST_STATUS_POLL,
        progress_callback=_debug_progress,
    )
    assert result is None

    container_timestamps_after = await _get_container_timestamps(container_names)

    for container_name in container_names:
        before: ContainerTimes = container_timestamps_before[container_name]
        after: ContainerTimes = container_timestamps_after[container_name]

        assert before.created == after.created
        assert before.started_at < after.started_at
        assert before.finished_at < after.finished_at
