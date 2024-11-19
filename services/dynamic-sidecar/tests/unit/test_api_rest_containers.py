# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
from collections.abc import AsyncIterable
from inspect import signature
from pathlib import Path
from typing import Any, AsyncIterator, Final
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import aiodocker
import aiofiles
import pytest
import yaml
from aiodocker.volumes import DockerVolume
from aiofiles.os import mkdir
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_dynamic_sidecar.containers import ActivityInfo
from models_library.services_creation import CreateServiceMetricsAdditionalParams
from models_library.services_io import ServiceOutput
from pydantic import TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from servicelib.docker_constants import SUFFIX_EGRESS_PROXY_NAME
from servicelib.fastapi.long_running_tasks.client import TaskId
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.api.rest.containers import _INACTIVE_FOR_LONG_TIME
from simcore_service_dynamic_sidecar.core.application import AppState
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    docker_compose_create,
)
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.core.utils import async_command
from simcore_service_dynamic_sidecar.core.validation import parse_compose_spec
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from simcore_service_dynamic_sidecar.modules.outputs._context import OutputsContext
from simcore_service_dynamic_sidecar.modules.outputs._manager import OutputsManager
from simcore_service_dynamic_sidecar.modules.outputs._watcher import OutputsWatcher
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

WAIT_FOR_OUTPUTS_WATCHER: Final[float] = 0.1
FAST_POLLING_INTERVAL: Final[float] = 0.1


# UTILS


class FailTestError(RuntimeError):
    pass


_TENACITY_RETRY_PARAMS: dict[str, Any] = {
    "reraise": True,
    "retry": retry_if_exception_type((FailTestError, AssertionError)),
    "stop": stop_after_delay(10),
    "wait": wait_fixed(0.01),
}


def _create_network_aliases(network_name: str) -> list[str]:
    return [f"alias_{i}_{network_name}" for i in range(10)]


async def _assert_enable_output_ports(test_client: TestClient) -> None:
    response = await test_client.patch(
        f"/{API_VTAG}/containers/ports/io",
        json={"enable_outputs": True, "enable_inputs": False},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def _assert_disable_output_ports(test_client: TestClient) -> None:
    response = await test_client.patch(
        f"/{API_VTAG}/containers/ports/io",
        json={"enable_outputs": False, "enable_inputs": False},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def _start_containers(
    test_client: TestClient,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
) -> list[str]:
    # start containers
    response = await test_client.post(
        f"/{API_VTAG}/containers/compose-spec",
        json={"docker_compose_yaml": compose_spec},
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    assert response.json() is None

    response = await test_client.post(
        f"/{API_VTAG}/containers",
        json={"metrics_params": mock_metrics_params.model_dump()},
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    task_id: TaskId = response.json()

    async for attempt in AsyncRetrying(
        wait=wait_fixed(FAST_POLLING_INTERVAL),
        stop=stop_after_delay(100 * FAST_POLLING_INTERVAL),
        reraise=True,
    ):
        with attempt:
            response = await test_client.get(f"/task/{task_id}")
            assert response.status_code == status.HTTP_200_OK
            task_status = response.json()
            if not task_status["done"]:
                msg = f"Waiting for task to complete, got: {task_status}"
                raise RuntimeError(msg)

    response = await test_client.get(f"/task/{task_id}/result")
    assert response.status_code == status.HTTP_200_OK
    result_response = response.json()
    assert result_response["error"] is None
    response_containers = result_response["result"]

    shared_store: SharedStore = test_client.application.state.shared_store
    container_names = shared_store.container_names
    assert response_containers == container_names

    return container_names


async def _docker_ps_a_container_names() -> list[str]:
    # TODO: replace with aiodocker this is legacy by now
    command = 'docker ps -a --format "{{.Names}}"'
    success, stdout, *_ = await async_command(command=command, timeout=None)

    assert success is True, stdout
    return stdout.split("\n")


async def _assert_compose_spec_pulled(compose_spec: str, settings: ApplicationSettings):
    """ensures all containers inside compose_spec are pulled"""

    result = await docker_compose_create(compose_spec, settings)

    assert result.success is True, result.message

    dict_compose_spec = json.loads(compose_spec)
    expected_services_count = len(dict_compose_spec["services"])

    docker_ps_names = await _docker_ps_a_container_names()
    started_containers = [
        x
        for x in docker_ps_names
        if x.startswith(settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE)
    ]
    assert len(started_containers) == expected_services_count


@pytest.fixture
def mock_environment(mock_rabbitmq_envs: EnvVarsDict) -> EnvVarsDict:
    return mock_rabbitmq_envs


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    app.state.shared_store = SharedStore()  # emulate on_startup event
    return app


@pytest.fixture
def test_client(
    ensure_shared_store_dir: Path,
    ensure_run_in_sequence_context_is_empty: None,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers: AsyncIterator[None],
    test_client: TestClient,
) -> TestClient:
    """creates external volumes and provides a client to dy-sidecar service"""
    return test_client


@pytest.fixture
def dynamic_sidecar_network_name() -> str:
    return "entrypoint_container_network"


@pytest.fixture
def compose_spec(dynamic_sidecar_network_name: str) -> str:
    return json.dumps(
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


@pytest.fixture
def compose_spec_single_service() -> str:
    return json.dumps(
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


@pytest.fixture(params=["compose_spec", "compose_spec_single_service"])
def selected_spec(request, compose_spec: str, compose_spec_single_service: str) -> str:
    # check that fixture_name is present in this function's parameters
    fixture_name = request.param
    sig = signature(selected_spec)
    assert fixture_name in sig.parameters, (
        f"Provided fixture name {fixture_name} was not found "
        f"as a parameter in the signature {sig}"
    )

    # returns the parameter by name from the ones declared in the signature
    result: str = locals()[fixture_name]
    return result


@pytest.fixture
async def started_containers(
    test_client: TestClient,
    compose_spec: str,
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
) -> list[str]:
    settings: ApplicationSettings = test_client.application.state.settings
    await _assert_compose_spec_pulled(compose_spec, settings)

    return await _start_containers(test_client, compose_spec, mock_metrics_params)


@pytest.fixture
def not_started_containers() -> list[str]:
    return [f"missing-container-{i}" for i in range(5)]


@pytest.fixture
def mock_outputs_labels() -> dict[str, ServiceOutput]:
    return {
        "output_port_1": TypeAdapter(ServiceOutput).validate_python(
            ServiceOutput.model_config["json_schema_extra"]["examples"][3]
        ),
        "output_port_2": TypeAdapter(ServiceOutput).validate_python(
            ServiceOutput.model_config["json_schema_extra"]["examples"][3]
        ),
    }


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
def mock_aiodocker_containers_get(mocker: MockerFixture, faker: Faker) -> int:
    """raises a DockerError with a random HTTP status which is also returned"""
    mock_status_code = faker.random_int(1, 999)

    async def mock_get(*args: str, **kwargs: Any) -> None:
        raise aiodocker.exceptions.DockerError(
            status=mock_status_code, data={"message": "aiodocker_mocked_error"}
        )

    mocker.patch("aiodocker.containers.DockerContainers.get", side_effect=mock_get)

    return mock_status_code


@pytest.fixture
def mock_event_filter_enqueue(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> AsyncMock:
    mock = AsyncMock(return_value=None)
    outputs_watcher: OutputsWatcher = app.state.outputs_watcher
    monkeypatch.setattr(outputs_watcher._event_filter, "enqueue", mock)  # noqa: SLF001
    return mock


@pytest.fixture
async def mocked_port_key_events_queue_coro_get(
    app: FastAPI, mocker: MockerFixture
) -> Mock:
    outputs_context: OutputsContext = app.state.outputs_context

    target = getattr(outputs_context.port_key_events_queue, "coro_get")  # noqa: B009

    mock_result_tracker = Mock()

    async def _wrapped_coroutine() -> Any:
        # NOTE: coro_get returns a future, naming is unfortunate
        # and can cause confusion, normally an async def function
        # will return a coroutine not a future object.
        future: asyncio.Future = target()
        result = await future
        mock_result_tracker(result)

        return result

    mocker.patch.object(
        outputs_context.port_key_events_queue,
        "coro_get",
        side_effect=_wrapped_coroutine,
    )

    return mock_result_tracker


# TESTS


def test_ensure_api_vtag_is_v1():
    assert API_VTAG == "v1"


async def test_start_same_space_twice(compose_spec: str, test_client: TestClient):
    settings = test_client.application.state.settings

    settings_1 = settings.model_copy(
        update={"DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "test_name_space_1"}, deep=True
    )
    await _assert_compose_spec_pulled(compose_spec, settings_1)

    settings_2 = settings.model_copy(
        update={"DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "test_name_space_2"}, deep=True
    )
    await _assert_compose_spec_pulled(compose_spec, settings_2)


async def test_containers_get(
    test_client: TestClient,
    started_containers: list[str],
    ensure_external_volumes: None,
):
    response = await test_client.get(f"/{API_VTAG}/containers")
    assert response.status_code == status.HTTP_200_OK, response.text

    decoded_response = response.json()
    assert set(decoded_response) == set(started_containers)
    for entry in decoded_response.values():
        assert "Status" not in entry
        assert "Error" not in entry


async def test_containers_get_status(
    test_client: TestClient,
    started_containers: list[str],
    ensure_external_volumes: None,
):
    response = await test_client.get(
        f"/{API_VTAG}/containers", query_string={"only_status": True}
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    decoded_response = response.json()
    assert set(decoded_response) == set(started_containers)

    def assert_keys_exist(result: dict[str, Any]) -> bool:
        for entry in result.values():
            assert "Status" in entry
            assert "Error" in entry
        return True

    assert assert_keys_exist(decoded_response) is True


async def test_containers_docker_status_docker_error(
    test_client: TestClient,
    started_containers: list[str],
    mock_aiodocker_containers_get: int,
):
    response = await test_client.get(f"/{API_VTAG}/containers")
    assert response.status_code == mock_aiodocker_containers_get, response.text


async def test_container_inspect_logs_remove(
    test_client: TestClient, started_containers: list[str]
):
    for container in started_containers:
        # get container logs
        # FIXME: slow call?
        response = await test_client.get(f"/{API_VTAG}/containers/{container}/logs")
        assert response.status_code == status.HTTP_200_OK, response.text

        # inspect container
        response = await test_client.get(f"/{API_VTAG}/containers/{container}")
        assert response.status_code == status.HTTP_200_OK, response.text
        parsed_response = response.json()
        assert parsed_response["Name"] == f"/{container}"


async def test_container_logs_with_timestamps(
    test_client: TestClient, started_containers: list[str]
):
    for container in started_containers:
        print("getting logs of container", container, "...")
        response = await test_client.get(
            f"/{API_VTAG}/containers/{container}/logs",
            query_string={"timestamps": True},
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == []


async def test_container_missing_container(
    test_client: TestClient, not_started_containers: list[str]
):
    def _expected_error_string(container: str) -> dict[str, str]:
        return {
            "detail": f"No container '{container}' was started. Started containers '[]'"
        }

    for container in not_started_containers:
        # get container logs
        response = await test_client.get(f"/{API_VTAG}/containers/{container}/logs")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert response.json() == _expected_error_string(container)

        # inspect container
        response = await test_client.get(f"/{API_VTAG}/containers/{container}")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert response.json() == _expected_error_string(container)


async def test_container_docker_error(
    test_client: TestClient,
    started_containers: list[str],
    mock_aiodocker_containers_get: int,
):
    def _expected_error_string(status_code: int) -> dict[str, Any]:
        return {
            "errors": [
                f"An unexpected Docker error occurred status_code={status_code}, message=aiodocker_mocked_error"
            ]
        }

    for container in started_containers:
        # get container logs
        response = await test_client.get(f"/{API_VTAG}/containers/{container}/logs")
        assert response.status_code == mock_aiodocker_containers_get, response.text
        assert response.json() == _expected_error_string(mock_aiodocker_containers_get)

        # inspect container
        response = await test_client.get(f"/{API_VTAG}/containers/{container}")
        assert response.status_code == mock_aiodocker_containers_get, response.text
        assert response.json() == _expected_error_string(mock_aiodocker_containers_get)


async def test_outputs_watcher_disabling(
    test_client: TestClient,
    mocked_port_key_events_queue_coro_get: Mock,
    mock_event_filter_enqueue: AsyncMock,
):
    assert isinstance(test_client.application, FastAPI)
    outputs_context: OutputsContext = test_client.application.state.outputs_context
    outputs_manager: OutputsManager = test_client.application.state.outputs_manager
    outputs_manager.task_monitor_interval_s = WAIT_FOR_OUTPUTS_WATCHER / 10

    async def _create_port_key_events(is_propagation_enabled: bool) -> None:
        random_subdir = f"{uuid4()}"

        await outputs_context.set_file_type_port_keys([random_subdir])

        dir_name = outputs_context.outputs_path / random_subdir
        await mkdir(dir_name)
        async with aiofiles.open(dir_name / f"file_{uuid4()}", "w") as f:
            await f.write("ok")

        EXPECTED_EVENTS_PER_RANDOM_PORT_KEY = 2

        async for attempt in AsyncRetrying(**_TENACITY_RETRY_PARAMS):
            with attempt:
                # check events were triggered after generation
                events_in_dir: list[str] = [
                    c.args[0]
                    for c in mocked_port_key_events_queue_coro_get.call_args_list
                    if c.args[0] == random_subdir
                ]

                if is_propagation_enabled:
                    assert len(events_in_dir) >= EXPECTED_EVENTS_PER_RANDOM_PORT_KEY
                else:
                    assert len(events_in_dir) == 0

    def _assert_events_generated(*, expected_events: int) -> None:
        events_set = {x.args[0] for x in mock_event_filter_enqueue.call_args_list}
        assert len(events_set) == expected_events

    # by default outputs-watcher it is disabled
    _assert_events_generated(expected_events=0)
    await _create_port_key_events(is_propagation_enabled=False)
    _assert_events_generated(expected_events=0)

    # after enabling new events will be generated
    await _assert_enable_output_ports(test_client)
    _assert_events_generated(expected_events=0)
    await _create_port_key_events(is_propagation_enabled=True)
    _assert_events_generated(expected_events=1)

    # disabling again, no longer generate events
    await _assert_disable_output_ports(test_client)
    _assert_events_generated(expected_events=1)
    await _create_port_key_events(is_propagation_enabled=False)
    _assert_events_generated(expected_events=1)

    # enabling once more time, events are once again generated
    await _assert_enable_output_ports(test_client)
    _assert_events_generated(expected_events=1)
    for i in range(10):
        await _create_port_key_events(is_propagation_enabled=True)
        _assert_events_generated(expected_events=2 + i)


async def test_container_create_outputs_dirs(
    test_client: TestClient,
    mock_outputs_labels: dict[str, ServiceOutput],
    mock_event_filter_enqueue: AsyncMock,
):
    assert isinstance(test_client.application, FastAPI)
    mounted_volumes = AppState(test_client.application).mounted_volumes

    # by default outputs-watcher it is disabled
    await _assert_enable_output_ports(test_client)
    await asyncio.sleep(WAIT_FOR_OUTPUTS_WATCHER)

    assert mock_event_filter_enqueue.call_count == 0

    json_outputs_labels = {
        k: v.model_dump(by_alias=True) for k, v in mock_outputs_labels.items()
    }
    response = await test_client.post(
        f"/{API_VTAG}/containers/ports/outputs/dirs",
        json={"outputs_labels": json_outputs_labels},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""

    for dir_name in mock_outputs_labels:
        assert (mounted_volumes.disk_outputs_path / dir_name).is_dir()

    await asyncio.sleep(WAIT_FOR_OUTPUTS_WATCHER)
    EXPECT_EVENTS_WHEN_CREATING_OUTPUT_PORT_KEY_DIRS = 0
    assert (
        mock_event_filter_enqueue.call_count
        == EXPECT_EVENTS_WHEN_CREATING_OUTPUT_PORT_KEY_DIRS
    )


def _get_entrypoint_container_name(test_client: TestClient) -> str:
    parsed_spec = parse_compose_spec(
        test_client.application.state.shared_store.compose_spec
    )
    container_name = None
    for service_name, service_details in parsed_spec["services"].items():
        if service_details.get("labels", None) is not None:
            container_name = service_name
            break
    assert container_name is not None
    return container_name


@pytest.mark.parametrize("include_exclude_filter_option", [True, False])
async def test_containers_entrypoint_name_ok(
    test_client: TestClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
    include_exclude_filter_option: bool,
):
    filters_dict = {"network": dynamic_sidecar_network_name}
    if include_exclude_filter_option:
        filters_dict["exclude"] = SUFFIX_EGRESS_PROXY_NAME
    filters = json.dumps(filters_dict)

    response = await test_client.get(f"/{API_VTAG}/containers/name?filters={filters}")
    assert response.status_code == status.HTTP_200_OK, response.text
    container_name = response.json()
    assert container_name == _get_entrypoint_container_name(test_client)
    assert SUFFIX_EGRESS_PROXY_NAME not in container_name


@pytest.mark.parametrize("include_exclude_filter_option", [True, False])
async def test_containers_entrypoint_name_containers_not_started(
    test_client: TestClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
    include_exclude_filter_option: bool,
):
    entrypoint_container = _get_entrypoint_container_name(test_client)

    # remove the container from the spec
    parsed_spec = parse_compose_spec(
        test_client.application.state.shared_store.compose_spec
    )
    del parsed_spec["services"][entrypoint_container]
    test_client.application.state.shared_store.compose_spec = yaml.safe_dump(
        parsed_spec
    )

    filters_dict = {"network": dynamic_sidecar_network_name}
    if include_exclude_filter_option:
        filters_dict["exclude"] = SUFFIX_EGRESS_PROXY_NAME
    filters = json.dumps(filters_dict)
    response = await test_client.get(f"/{API_VTAG}/containers/name?filters={filters}")

    if include_exclude_filter_option:
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert response.json() == {
            "detail": "No container found for network=entrypoint_container_network"
        }
    else:
        assert response.status_code == status.HTTP_200_OK, response.text
        found_container = response.json()
        assert found_container in started_containers
        assert SUFFIX_EGRESS_PROXY_NAME in found_container


async def test_attach_detach_container_to_network(
    docker_swarm: None,
    test_client: TestClient,
    selected_spec: str,
    attachable_networks_and_ids: dict[str, str],
    mock_metrics_params: CreateServiceMetricsAdditionalParams,
):
    container_names = await _start_containers(
        test_client, selected_spec, mock_metrics_params
    )

    async with aiodocker.Docker() as docker:
        for container_name in container_names:
            for network_name, network_id in attachable_networks_and_ids.items():
                network_aliases = _create_network_aliases(network_name)

                # attach network to containers
                for _ in range(2):  # calling 2 times in a row
                    response = await test_client.post(
                        f"/{API_VTAG}/containers/{container_name}/networks:attach",
                        json={
                            "network_id": network_id,
                            "network_aliases": network_aliases,
                        },
                    )
                    assert (
                        response.status_code == status.HTTP_204_NO_CONTENT
                    ), response.text

                container = await docker.containers.get(container_name)
                container_inspect = await container.show()
                networks = container_inspect["NetworkSettings"]["Networks"]
                assert network_id in networks
                assert set(network_aliases).issubset(
                    set(networks[network_id]["Aliases"])
                )

                # detach network from containers
                for _ in range(2):  # running twice in a row
                    response = await test_client.post(
                        f"/{API_VTAG}/containers/{container_name}/networks:detach",
                        json={"network_id": network_id},
                    )
                    assert (
                        response.status_code == status.HTTP_204_NO_CONTENT
                    ), response.text

                container = await docker.containers.get(container_name)
                container_inspect = await container.show()
                networks = container_inspect["NetworkSettings"]["Networks"]
                assert network_id not in networks


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
    shared_store.original_to_container_names[
        "mock_container_name"
    ] = "mock_container_name"


async def test_containers_activity_command_failed(
    define_inactivity_command: None, test_client: TestClient, mock_shared_store: None
):
    response = await test_client.get(f"/{API_VTAG}/containers/activity")
    assert response.status_code == 200, response.text
    assert (
        response.json()
        == ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME).model_dump()
    )


async def test_containers_activity_no_inactivity_defined(
    test_client: TestClient, mock_shared_store: None
):
    response = await test_client.get(f"/{API_VTAG}/containers/activity")
    assert response.status_code == 200, response.text
    assert response.json() is None


@pytest.fixture
def activity_response() -> ActivityInfo:
    return ActivityInfo(seconds_inactive=10)


@pytest.fixture
def mock_inactive_since_command_response(
    mocker: MockerFixture,
    activity_response: ActivityInfo,
) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.api.rest.containers.run_command_in_container",
        return_value=activity_response.model_dump_json(),
    )


async def test_containers_activity_inactive_since(
    define_inactivity_command: None,
    mock_inactive_since_command_response: None,
    test_client: TestClient,
    mock_shared_store: None,
    activity_response: ActivityInfo,
):
    response = await test_client.get(f"/{API_VTAG}/containers/activity")
    assert response.status_code == 200, response.text
    assert response.json() == activity_response.model_dump()


@pytest.fixture
def mock_inactive_response_wrong_format(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.api.rest.containers.run_command_in_container",
        return_value="This is an unparsable json response {}",
    )


async def test_containers_activity_unexpected_response(
    define_inactivity_command: None,
    mock_inactive_response_wrong_format: None,
    test_client: TestClient,
    mock_shared_store: None,
):
    response = await test_client.get(f"/{API_VTAG}/containers/activity")
    assert response.status_code == 200, response.text
    assert (
        response.json()
        == ActivityInfo(seconds_inactive=_INACTIVE_FOR_LONG_TIME).model_dump()
    )
