# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
import asyncio
import json
from collections.abc import AsyncIterable
from inspect import signature
from typing import Any, Final
from unittest.mock import AsyncMock

import aiodocker
import pytest
import yaml
from aiodocker.volumes import DockerVolume
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import (
    ContainersComposeSpec,
    ContainersCreate,
)
from models_library.api_schemas_dynamic_sidecar.containers import ActivityInfo
from models_library.projects_nodes_io import NodeID
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from models_library.services_io import ServiceOutput
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.docker_constants import SUFFIX_EGRESS_PROXY_NAME
from servicelib.fastapi.long_running_tasks._manager import FastAPILongRunningManager
from servicelib.long_running_tasks.models import LRTNamespace
from servicelib.rabbitmq import RabbitMQRPCClient, RPCServerError
from servicelib.rabbitmq.rpc_interfaces.dynamic_sidecar import (
    container_extensions,
    containers,
    containers_long_running_tasks,
)
from simcore_service_dynamic_sidecar.core.application import AppState
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    docker_compose_create,
)
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.core.utils import async_command
from simcore_service_dynamic_sidecar.core.validation import parse_compose_spec
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules.inputs import InputsState
from simcore_service_dynamic_sidecar.modules.outputs._watcher import OutputsWatcher
from simcore_service_dynamic_sidecar.services.containers import _INACTIVE_FOR_LONG_TIME
from utils import get_lrt_result

pytest_simcore_core_services_selection = [
    "rabbit",
]

_WAIT_FOR_OUTPUTS_WATCHER: Final[float] = 0.1


def _assert_inputs_pulling(app: FastAPI, is_enabled: bool) -> None:
    inputs_state: InputsState = app.state.inputs_state
    assert inputs_state.inputs_pulling_enabled is is_enabled


def _assert_outputs_event_propagation(
    spy_output_watcher: dict[str, AsyncMock], is_enabled: bool
) -> None:
    assert spy_output_watcher["disable_event_propagation"].call_count == (
        1 if not is_enabled else 0
    )
    assert spy_output_watcher["enable_event_propagation"].call_count == (
        1 if is_enabled else 0
    )


@pytest.fixture
def spy_output_watcher(mocker: MockerFixture) -> dict[str, AsyncMock]:
    return {
        "disable_event_propagation": mocker.spy(
            OutputsWatcher, "disable_event_propagation"
        ),
        "enable_event_propagation": mocker.spy(
            OutputsWatcher, "enable_event_propagation"
        ),
    }


@pytest.mark.parametrize("enabled", [True, False])
async def test_toggle_ports_io(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    enabled: bool,
    spy_output_watcher: dict[str, AsyncMock],
):
    settings: ApplicationSettings = app.state.settings

    result = await container_extensions.toggle_ports_io(
        rpc_client,
        node_id=settings.DY_SIDECAR_NODE_ID,
        enable_outputs=enabled,
        enable_inputs=enabled,
    )
    assert result is None

    _assert_inputs_pulling(app, enabled)
    _assert_outputs_event_propagation(spy_output_watcher, enabled)


@pytest.fixture
def mock_outputs_labels() -> dict[str, ServiceOutput]:
    return {
        "output_port_1": TypeAdapter(ServiceOutput).validate_python(
            ServiceOutput.model_json_schema()["examples"][3]
        ),
        "output_port_2": TypeAdapter(ServiceOutput).validate_python(
            ServiceOutput.model_json_schema()["examples"][3]
        ),
    }


@pytest.fixture
def mock_event_filter_enqueue(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> AsyncMock:
    mock = AsyncMock(return_value=None)
    outputs_watcher: OutputsWatcher = app.state.outputs_watcher
    monkeypatch.setattr(outputs_watcher._event_filter, "enqueue", mock)  # noqa: SLF001
    return mock


async def test_container_create_outputs_dirs(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_outputs_labels: dict[str, ServiceOutput],
    mock_event_filter_enqueue: AsyncMock,
):
    app_state = AppState(app)

    # by default outputs-watcher it is disabled
    result = await container_extensions.toggle_ports_io(
        rpc_client,
        node_id=app_state.settings.DY_SIDECAR_NODE_ID,
        enable_outputs=True,
        enable_inputs=True,
    )
    assert result is None
    await asyncio.sleep(_WAIT_FOR_OUTPUTS_WATCHER)

    assert mock_event_filter_enqueue.call_count == 0

    result = await container_extensions.create_output_dirs(
        rpc_client,
        node_id=app_state.settings.DY_SIDECAR_NODE_ID,
        outputs_labels=mock_outputs_labels,
    )

    for dir_name in mock_outputs_labels:
        assert (app_state.mounted_volumes.disk_outputs_path / dir_name).is_dir()

    await asyncio.sleep(_WAIT_FOR_OUTPUTS_WATCHER)
    EXPECT_EVENTS_WHEN_CREATING_OUTPUT_PORT_KEY_DIRS = 0
    assert (
        mock_event_filter_enqueue.call_count
        == EXPECT_EVENTS_WHEN_CREATING_OUTPUT_PORT_KEY_DIRS
    )


@pytest.fixture
async def attachable_networks_and_ids(faker: Faker) -> AsyncIterable[dict[str, str]]:
    # generate some network names
    unique_id = faker.uuid4()
    network_names = {f"test_network_{i}_{unique_id}": "" for i in range(10)}

    # create networks
    async with aiodocker.Docker() as client:
        for network_name in network_names:
            network_config = {
                "Name": network_name,
                "Driver": "overlay",
                "Attachable": True,
                "Internal": True,
            }
            network = await client.networks.create(network_config)
            network_names[network_name] = network.id

    yield network_names

    # remove networks
    async with aiodocker.Docker() as client:
        for network_id in network_names.values():
            network = await client.networks.get(network_id)
            assert await network.delete() is True


@pytest.fixture
def dynamic_sidecar_network_name() -> str:
    return "entrypoint_container_network"


@pytest.fixture
def compose_spec(dynamic_sidecar_network_name: str) -> ContainersComposeSpec:
    return ContainersComposeSpec(
        docker_compose_yaml=yaml.dump(
            {
                "version": "3",
                "services": {
                    "first-box": {
                        "image": "busybox:latest",
                        "networks": {
                            dynamic_sidecar_network_name: None,
                        },
                        "labels": {"io.osparc.test-label": "mark-entrypoint"},
                    },
                    "second-box": {"image": "busybox:latest"},
                    "egress": {
                        "image": "busybox:latest",
                        "networks": {
                            dynamic_sidecar_network_name: None,
                        },
                    },
                },
                "networks": {dynamic_sidecar_network_name: None},
            }
        )
    )


@pytest.fixture
def compose_spec_single_service() -> ContainersComposeSpec:
    return ContainersComposeSpec(
        docker_compose_yaml=yaml.dump(
            {
                "version": "3",
                "services": {
                    "solo-box": {
                        "image": "busybox:latest",
                        "labels": {"io.osparc.test-label": "mark-entrypoint"},
                    },
                },
            }
        )
    )


@pytest.fixture(params=["compose_spec", "compose_spec_single_service"])
def selected_spec(
    request, compose_spec: str, compose_spec_single_service: str
) -> ContainersComposeSpec:
    # check that fixture_name is present in this function's parameters
    fixture_name = request.param
    sig = signature(selected_spec)
    assert fixture_name in sig.parameters, (
        f"Provided fixture name {fixture_name} was not found "
        f"as a parameter in the signature {sig}"
    )

    # returns the parameter by name from the ones declared in the signature
    result: ContainersComposeSpec = locals()[fixture_name]
    return result


@pytest.fixture
def lrt_namespace(app: FastAPI) -> LRTNamespace:
    long_running_manager: FastAPILongRunningManager = app.state.long_running_manager
    return long_running_manager.lrt_namespace


_FAST_STATUS_POLL: Final[float] = 0.1
_CREATE_SERVICE_CONTAINERS_TIMEOUT: Final[float] = 60


async def _start_containers(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    compose_spec: ContainersComposeSpec,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
) -> list[str]:
    await containers.create_compose_spec(
        rpc_client, node_id=node_id, containers_compose_spec=compose_spec
    )

    containers_create = ContainersCreate(metrics_params=mock_metrics_params)
    task_id = await containers_long_running_tasks.create_user_services(
        rpc_client,
        node_id=node_id,
        lrt_namespace=lrt_namespace,
        containers_create=containers_create,
    )

    response_containers = await get_lrt_result(
        rpc_client,
        lrt_namespace,
        task_id,
        status_poll_interval=_FAST_STATUS_POLL,
        task_timeout=_CREATE_SERVICE_CONTAINERS_TIMEOUT,
    )

    shared_store: SharedStore = app.state.shared_store
    container_names = shared_store.container_names
    assert response_containers == container_names

    return container_names


def _create_network_aliases(network_name: str) -> list[str]:
    return [f"alias_{i}_{network_name}" for i in range(10)]


async def test_attach_detach_container_to_network(
    ensure_external_volumes: tuple[DockerVolume],
    docker_swarm: None,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    selected_spec: ContainersComposeSpec,
    attachable_networks_and_ids: dict[str, str],
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
):
    app_state = AppState(app)

    container_names = await _start_containers(
        app,
        rpc_client,
        node_id=app_state.settings.DY_SIDECAR_NODE_ID,
        lrt_namespace=lrt_namespace,
        compose_spec=selected_spec,
        mock_metrics_params=mock_metrics_params,
    )

    async with aiodocker.Docker() as docker:
        for container_name in container_names:
            for network_name, network_id in attachable_networks_and_ids.items():
                network_aliases = _create_network_aliases(network_name)

                # attach network to containers
                for _ in range(2):  # calling 2 times in a row
                    await container_extensions.attach_container_to_network(
                        rpc_client,
                        node_id=app_state.settings.DY_SIDECAR_NODE_ID,
                        container_id=container_name,
                        network_id=network_id,
                        network_aliases=network_aliases,
                    )

                container = await docker.containers.get(container_name)
                container_inspect = await container.show()
                networks = container_inspect["NetworkSettings"]["Networks"]
                assert network_id in networks
                assert set(network_aliases).issubset(
                    set(networks[network_id]["Aliases"])
                )

                # detach network from containers
                for _ in range(2):  # running twice in a row
                    await container_extensions.detach_container_from_network(
                        rpc_client,
                        node_id=app_state.settings.DY_SIDECAR_NODE_ID,
                        container_id=container_name,
                        network_id=network_id,
                    )

                container = await docker.containers.get(container_name)
                container_inspect = await container.show()
                networks = container_inspect["NetworkSettings"]["Networks"]
                assert network_id not in networks


async def _docker_ps_a_container_names() -> list[str]:
    command = 'docker ps -a --format "{{.Names}}"'
    success, stdout, *_ = await async_command(command=command, timeout=None)

    assert success is True, stdout
    return stdout.split("\n")


async def _assert_compose_spec_pulled(
    docker_compose_yaml: str, settings: ApplicationSettings
):
    """ensures all containers inside compose_spec are pulled"""

    result = await docker_compose_create(docker_compose_yaml, settings)

    assert result.success is True, result.message

    dict_compose_spec = yaml.safe_load(docker_compose_yaml)
    expected_services_count = len(dict_compose_spec["services"])

    docker_ps_names = await _docker_ps_a_container_names()
    started_containers = [
        x
        for x in docker_ps_names
        if x.startswith(settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE)
    ]
    assert len(started_containers) == expected_services_count


@pytest.fixture
async def started_containers(
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    node_id: NodeID,
    lrt_namespace: LRTNamespace,
    compose_spec: ContainersComposeSpec,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
) -> list[str]:
    settings: ApplicationSettings = app.state.settings
    await _assert_compose_spec_pulled(compose_spec.docker_compose_yaml, settings)

    return await _start_containers(
        app,
        rpc_client,
        node_id=node_id,
        lrt_namespace=lrt_namespace,
        compose_spec=compose_spec,
        mock_metrics_params=mock_metrics_params,
    )


async def test_containers_get(
    ensure_external_volumes: tuple[DockerVolume],
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    lrt_namespace: LRTNamespace,
    started_containers: list[str],
):
    app_state = AppState(app)
    containers_inspect = await containers.containers_docker_inspect(
        rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID, only_status=False
    )

    assert set(containers_inspect) == set(started_containers)
    for entry in containers_inspect.values():
        assert "Status" not in entry
        assert "Error" not in entry


async def test_containers_get_status(
    ensure_external_volumes: tuple[DockerVolume],
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    started_containers: list[str],
):
    app_state = AppState(app)
    containers_inspect = await containers.containers_docker_inspect(
        rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID, only_status=True
    )
    assert set(containers_inspect) == set(started_containers)

    def _assert_keys_exist(result: dict[str, Any]) -> bool:
        for entry in result.values():
            assert "Status" in entry
            assert "Error" in entry
        return True

    assert _assert_keys_exist(containers_inspect) is True


@pytest.fixture
def mock_aiodocker_containers_get(mocker: MockerFixture, faker: Faker) -> int:
    """raises a DockerError with a random HTTP status which is also returned"""
    mock_status_code = faker.random_int(1, 999)

    async def mock_get(*args: str, **kwargs: Any) -> None:
        raise aiodocker.exceptions.DockerError(
            status=mock_status_code, data={"message": "aiodocker_mocked_error"}
        )

    mocker.patch("aiodocker.containers.DockerContainers.get", side_effect=mock_get)

    return mock_status_code


async def test_containers_docker_status_docker_error(
    ensure_external_volumes: tuple[DockerVolume],
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    started_containers: list[str],
    mock_aiodocker_containers_get: int,
):
    app_state = AppState(app)
    with pytest.raises(
        RPCServerError, match=f"status_code={mock_aiodocker_containers_get}"
    ):
        await containers.containers_docker_inspect(
            rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID, only_status=True
        )


@pytest.fixture
def define_inactivity_command(
    mock_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> None:
    setenvs_from_dict(
        monkeypatch,
        {
            "DY_SIDECAR_CALLBACKS_MAPPING": json.dumps(
                {
                    "inactivity": {
                        "service": "mock_container_name",
                        "command": "",
                        "timeout": 4,
                    }
                }
            )
        },
    )


@pytest.fixture
def mock_shared_store(app: FastAPI) -> None:
    shared_store: SharedStore = app.state.shared_store
    shared_store.original_to_container_names["mock_container_name"] = (
        "mock_container_name"
    )


async def test_containers_activity_command_failed(
    define_inactivity_command: None,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_shared_store: None,
):
    app_state = AppState(app)
    containers_activity = await containers.get_containers_activity(
        rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID
    )
    assert containers_activity == ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME)


async def test_containers_activity_no_inactivity_defined(
    app: FastAPI, rpc_client: RabbitMQRPCClient, mock_shared_store: None
):
    app_state = AppState(app)
    containers_activity = await containers.get_containers_activity(
        rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID
    )
    assert containers_activity is None


@pytest.fixture
def activity_response() -> ActivityInfo:
    return ActivityInfo(seconds_inactive=10)


@pytest.fixture
def mock_inactive_since_command_response(
    mocker: MockerFixture,
    activity_response: ActivityInfo,
) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.services.containers.run_command_in_container",
        return_value=activity_response.model_dump_json(),
    )


async def test_containers_activity_inactive_since(
    define_inactivity_command: None,
    mock_inactive_since_command_response: None,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_shared_store: None,
    activity_response: ActivityInfo,
):
    app_state = AppState(app)
    containers_activity = await containers.get_containers_activity(
        rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID
    )
    assert containers_activity == activity_response


@pytest.fixture
def mock_inactive_response_wrong_format(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.services.containers.run_command_in_container",
        return_value="This is an unparsable json response {}",
    )


async def test_containers_activity_unexpected_response(
    define_inactivity_command: None,
    mock_inactive_response_wrong_format: None,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    mock_shared_store: None,
):
    app_state = AppState(app)
    containers_activity = await containers.get_containers_activity(
        rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID
    )
    assert containers_activity == ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME)


def _get_entrypoint_container_name(app: FastAPI) -> str:
    parsed_spec = parse_compose_spec(app.state.shared_store.compose_spec)
    container_name = None
    for service_name, service_details in parsed_spec["services"].items():
        # a trick to fetch the expected container
        if service_details.get("labels", None) is not None:
            container_name = service_name
            break
    assert container_name is not None
    return container_name


@pytest.mark.parametrize("include_exclude_filter_option", [True, False])
async def test_containers_entrypoint_name_ok(
    ensure_external_volumes: tuple[DockerVolume],
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
    include_exclude_filter_option: bool,
):
    app_state = AppState(app)

    filters_dict = {"network": dynamic_sidecar_network_name}
    if include_exclude_filter_option:
        filters_dict["exclude"] = SUFFIX_EGRESS_PROXY_NAME
    filters = json.dumps(filters_dict)

    container_name = await containers.get_containers_name(
        rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID, filters=filters
    )
    if include_exclude_filter_option:
        assert container_name == _get_entrypoint_container_name(app)
        assert SUFFIX_EGRESS_PROXY_NAME not in container_name
    else:
        assert SUFFIX_EGRESS_PROXY_NAME in container_name


@pytest.mark.parametrize("include_exclude_filter_option", [True, False])
async def test_containers_entrypoint_name_containers_not_started(
    ensure_external_volumes: tuple[DockerVolume],
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
    include_exclude_filter_option: bool,
):
    app_state = AppState(app)

    entrypoint_container = _get_entrypoint_container_name(app)

    # remove the container from the spec
    parsed_spec = parse_compose_spec(app.state.shared_store.compose_spec)
    del parsed_spec["services"][entrypoint_container]
    app.state.shared_store.compose_spec = yaml.safe_dump(parsed_spec)

    filters_dict = {"network": dynamic_sidecar_network_name}
    if include_exclude_filter_option:
        filters_dict["exclude"] = SUFFIX_EGRESS_PROXY_NAME
    filters = json.dumps(filters_dict)

    if include_exclude_filter_option:
        with pytest.raises(
            RPCServerError,
            match="No container found for network=entrypoint_container_network and exclude=egress",
        ):
            await containers.get_containers_name(
                rpc_client,
                node_id=app_state.settings.DY_SIDECAR_NODE_ID,
                filters=filters,
            )

    else:
        found_container = await containers.get_containers_name(
            rpc_client, node_id=app_state.settings.DY_SIDECAR_NODE_ID, filters=filters
        )
        assert found_container in started_containers
        assert SUFFIX_EGRESS_PROXY_NAME in found_container


@pytest.fixture
def not_started_containers() -> list[str]:
    return [f"missing-container-{i}" for i in range(5)]


async def test_container_missing_container(
    app: FastAPI, rpc_client: RabbitMQRPCClient, not_started_containers: list[str]
):
    app_state = AppState(app)

    for container in not_started_containers:
        with pytest.raises(
            RPCServerError,
            match=rf"No container='{container}' was found in started_containers='\[\]'",
        ):
            await containers.inspect_container(
                rpc_client,
                node_id=app_state.settings.DY_SIDECAR_NODE_ID,
                container_id=container,
            )


async def test_container_docker_error(
    ensure_external_volumes: tuple[DockerVolume],
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    started_containers: list[str],
    mock_aiodocker_containers_get: int,
):
    app_state = AppState(app)

    for container in started_containers:
        # inspect container
        with pytest.raises(
            RPCServerError,
            match=f"An unexpected Docker error occurred status_code={mock_aiodocker_containers_get}, message=aiodocker_mocked_error",
        ):
            await containers.inspect_container(
                rpc_client,
                node_id=app_state.settings.DY_SIDECAR_NODE_ID,
                container_id=container,
            )
