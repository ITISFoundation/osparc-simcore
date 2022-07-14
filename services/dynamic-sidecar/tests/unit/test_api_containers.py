# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import random
from collections import namedtuple
from inspect import signature
from typing import Any, AsyncIterable, Iterator
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import aiodocker
import faker
import pytest
import yaml
from aiodocker.containers import DockerContainer
from aiodocker.volumes import DockerVolume
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import FastAPI, status
from models_library.services import ServiceOutput
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from simcore_sdk.node_ports_common.exceptions import NodeNotFound
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.core.application import AppState
from simcore_service_dynamic_sidecar.core.docker_compose_utils import docker_compose_up
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.core.utils import HIDDEN_FILE_NAME, async_command
from simcore_service_dynamic_sidecar.core.validation import parse_compose_spec
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore

ContainerTimes = namedtuple("ContainerTimes", "created, started_at, finished_at")

DEFAULT_COMMAND_TIMEOUT = 5
WAIT_FOR_DIRECTORY_WATCHER = 0.1


# FIXTURES


@pytest.fixture
def client(
    test_client: TestClient,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers,
):
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
                    "image": "busybox",
                    "networks": [
                        dynamic_sidecar_network_name,
                    ],
                },
                "second-box": {"image": "busybox"},
            },
            "networks": {dynamic_sidecar_network_name: {}},
        }
    )


@pytest.fixture
def compose_spec_single_service() -> str:
    return json.dumps(
        {
            "version": "3",
            "services": {
                "solo-box": {"image": "busybox"},
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


async def _docker_ps_a_container_names() -> list[str]:
    command = 'docker ps -a --format "{{.Names}}"'
    success, stdout, *_ = await async_command(command=command, timeout=None)

    assert success is True, stdout
    return stdout.split("\n")


async def _assert_compose_spec_pulled(compose_spec: str, settings: ApplicationSettings):
    """ensures all containers inside compose_spec are pulled"""

    result = await docker_compose_up(compose_spec, settings)

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
async def started_containers(client: TestClient, compose_spec: str) -> list[str]:
    settings: ApplicationSettings = client.application.state.settings
    await _assert_compose_spec_pulled(compose_spec, settings)

    # start containers
    response = await client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": compose_spec}
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text

    shared_store: SharedStore = client.application.state.shared_store
    container_names = shared_store.container_names
    assert len(container_names) == 2
    assert response.json() == container_names

    return container_names


@pytest.fixture
def not_started_containers() -> list[str]:
    return [f"missing-container-{i}" for i in range(5)]


@pytest.fixture
def mock_nodeports(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.nodeports.upload_outputs",
        return_value=None,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.nodeports.download_target_ports",
        return_value=42,
    )


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


@pytest.fixture
def mock_port_keys() -> list[str]:
    return ["first_port", "second_port"]


@pytest.fixture
def mock_outputs_labels() -> dict[str, ServiceOutput]:
    return {
        "output_port_1": ServiceOutput.parse_obj(
            ServiceOutput.Config.schema_extra["examples"][3]
        ),
        "output_port_2": ServiceOutput.parse_obj(
            ServiceOutput.Config.schema_extra["examples"][3]
        ),
    }


@pytest.fixture
def rabbitmq_mock(mocker, app: FastAPI) -> None:
    app.state.rabbitmq = mocker.AsyncMock()


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


# UTILS


def _create_network_aliases(network_name: str) -> list[str]:
    return [f"alias_{i}_{network_name}" for i in range(10)]


async def _assert_enable_directory_watcher(client: TestClient) -> None:
    response = await client.patch(
        f"/{API_VTAG}/containers/directory-watcher", json=dict(is_enabled=True)
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def _assert_disable_directory_watcher(client: TestClient) -> None:
    response = await client.patch(
        f"/{API_VTAG}/containers/directory-watcher", json=dict(is_enabled=False)
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


# TESTS


def test_ensure_api_vtag_is_v1():
    assert API_VTAG == "v1"


async def test_start_containers_wrong_spec(client: TestClient, rabbitmq_mock: None):
    response = await client.post(
        f"/{API_VTAG}/containers",
        json={"docker_compose_yaml": "INVALID_COMPOSE_SPEC_YAML"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "yaml is not valid" in response.json()["detail"]


async def test_start_same_space_twice(
    compose_spec: str,
    client: TestClient,
):
    settings = client.application.state.settings

    settings_1 = settings.copy(
        update={"DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "test_name_space_1"}, deep=True
    )
    await _assert_compose_spec_pulled(compose_spec, settings_1)

    settings_2 = settings.copy(
        update={"DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "test_name_space_2"}, deep=True
    )
    await _assert_compose_spec_pulled(compose_spec, settings_2)


async def test_compose_up(client: TestClient, compose_spec: dict[str, Any]):
    response = await client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": compose_spec}
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    shared_store: SharedStore = client.application.state.shared_store
    container_names = shared_store.container_names
    assert response.json() == container_names


async def test_compose_up_spec_not_provided(client: TestClient):
    response = await client.post(f"/{API_VTAG}/containers")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    # FIXME: next PR, error schemas in OAS are NOT consistent with this check
    #  assert "yaml not valid" in response.json()["detail"]


async def test_compose_up_spec_invalid(client: TestClient):
    invalid_compose_spec = faker.Faker().text()  # pylint: disable=no-member
    response = await client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": invalid_compose_spec}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert "Provided yaml is not valid!" in response.text
    # 28+ characters means the compos spec is also present in the error message
    assert len(response.text) > 28


async def test_containers_down_after_starting(
    client: TestClient, compose_spec: dict[str, Any]
):
    # store spec first
    response = await client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": compose_spec}
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    shared_store: SharedStore = client.application.state.shared_store
    container_names = shared_store.container_names
    assert response.json() == container_names

    response = await client.post(
        f"/{API_VTAG}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.text != ""


async def test_containers_down_missing_spec(
    client: TestClient, compose_spec: dict[str, Any]
):
    response = await client.post(
        f"/{API_VTAG}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert "found" in response.json()["detail"]


async def test_containers_get(
    client: TestClient,
    started_containers: list[str],
    ensure_external_volumes: None,
):
    response = await client.get(f"/{API_VTAG}/containers")
    assert response.status_code == status.HTTP_200_OK, response.text

    decoded_response = response.json()
    assert set(decoded_response) == set(started_containers)
    for entry in decoded_response.values():
        assert "Status" not in entry
        assert "Error" not in entry


async def test_containers_get_status(
    client: TestClient,
    started_containers: list[str],
    ensure_external_volumes: None,
):
    response = await client.get(
        f"/{API_VTAG}/containers", query_string=dict(only_status=True)
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


@pytest.fixture
def mock_aiodocker_containers_get(mocker: MockerFixture) -> int:
    """raises a DockerError with a random HTTP status which is also returned"""
    mock_status_code = random.randint(1, 999)

    async def mock_get(*args: str, **kwargs: Any) -> None:
        raise aiodocker.exceptions.DockerError(
            status=mock_status_code, data=dict(message="aiodocker_mocked_error")
        )

    mocker.patch("aiodocker.containers.DockerContainers.get", side_effect=mock_get)

    return mock_status_code


async def test_containers_docker_status_docker_error(
    client: TestClient,
    started_containers: list[str],
    mock_aiodocker_containers_get: int,
):
    response = await client.get(f"/{API_VTAG}/containers")
    assert response.status_code == mock_aiodocker_containers_get, response.text


async def test_container_inspect_logs_remove(
    client: TestClient, started_containers: list[str]
):
    for container in started_containers:
        # get container logs
        # FIXME: slow call?
        response = await client.get(f"/{API_VTAG}/containers/{container}/logs")
        assert response.status_code == status.HTTP_200_OK, response.text

        # inspect container
        response = await client.get(f"/{API_VTAG}/containers/{container}")
        assert response.status_code == status.HTTP_200_OK, response.text
        parsed_response = response.json()
        assert parsed_response["Name"] == f"/{container}"


async def test_container_logs_with_timestamps(
    client: TestClient, started_containers: list[str]
):
    for container in started_containers:
        print("getting logs of container", container, "...")
        response = await client.get(
            f"/{API_VTAG}/containers/{container}/logs",
            query_string=dict(timestamps=True),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == []


async def test_container_missing_container(
    client: TestClient, not_started_containers: list[str]
):
    def _expected_error_string(container: str) -> dict[str, str]:
        return dict(
            detail=f"No container '{container}' was started. Started containers '[]'"
        )

    for container in not_started_containers:
        # get container logs
        response = await client.get(f"/{API_VTAG}/containers/{container}/logs")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert response.json() == _expected_error_string(container)

        # inspect container
        response = await client.get(f"/{API_VTAG}/containers/{container}")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert response.json() == _expected_error_string(container)


async def test_container_docker_error(
    client: TestClient,
    started_containers: list[str],
    mock_aiodocker_containers_get: int,
):
    def _expected_error_string(status_code: int) -> dict[str, Any]:
        return {
            "errors": [
                f"An unexpected Docker error occurred status={status_code}, message='aiodocker_mocked_error'"
            ]
        }

    for container in started_containers:
        # get container logs
        response = await client.get(f"/{API_VTAG}/containers/{container}/logs")
        assert response.status_code == mock_aiodocker_containers_get, response.text
        assert response.json() == _expected_error_string(mock_aiodocker_containers_get)

        # inspect container
        response = await client.get(f"/{API_VTAG}/containers/{container}")
        assert response.status_code == mock_aiodocker_containers_get, response.text
        assert response.json() == _expected_error_string(mock_aiodocker_containers_get)


async def test_container_save_state(client: TestClient, mock_data_manager: None):
    response = await client.post(f"/{API_VTAG}/containers/state:save")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def test_container_restore_state(client: TestClient, mock_data_manager: None):
    response = await client.post(f"/{API_VTAG}/containers/state:restore")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def test_container_pull_input_ports(
    client: TestClient, mock_port_keys: list[str], mock_nodeports: None
):
    response = await client.post(
        f"/{API_VTAG}/containers/ports/inputs:pull", json=mock_port_keys
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.text == "42"


@pytest.fixture
def mock_dir_watcher_on_any_event(
    app: FastAPI, monkeypatch: MonkeyPatch
) -> Iterator[Mock]:

    mock = Mock(return_value=None)

    monkeypatch.setattr(
        app.state.dir_watcher.outputs_event_handle, "_invoke_push_directory", mock
    )
    yield mock


async def test_directory_watcher_disabling(
    client: TestClient,
    mock_dir_watcher_on_any_event: AsyncMock,
):
    assert isinstance(client.application, FastAPI)
    mounted_volumes = AppState(client.application).mounted_volumes

    def _create_random_dir_in_inputs() -> int:
        dir_name = mounted_volumes.disk_outputs_path / f"{uuid4()}"
        dir_name.mkdir(parents=True)
        dir_count = len(
            [
                1
                for x in mounted_volumes.disk_outputs_path.glob("*")
                if not f"{x}".endswith(HIDDEN_FILE_NAME)
            ]
        )
        return dir_count

    EVENTS_PER_DIR_CREATION = 2

    # by default directory-watcher it is disabled
    await _assert_enable_directory_watcher(client)
    assert mock_dir_watcher_on_any_event.call_count == 0
    dir_count = _create_random_dir_in_inputs()
    assert dir_count == 1
    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == EVENTS_PER_DIR_CREATION

    # disable and wait for events should have the same count as before
    await _assert_disable_directory_watcher(client)
    dir_count = _create_random_dir_in_inputs()
    assert dir_count == 2
    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == EVENTS_PER_DIR_CREATION

    # enable and wait for events
    await _assert_enable_directory_watcher(client)
    dir_count = _create_random_dir_in_inputs()
    assert dir_count == 3
    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == 2 * EVENTS_PER_DIR_CREATION


async def test_container_create_outputs_dirs(
    client: TestClient,
    mock_outputs_labels: dict[str, ServiceOutput],
    mock_dir_watcher_on_any_event: AsyncMock,
):
    assert isinstance(client.application, FastAPI)
    mounted_volumes = AppState(client.application).mounted_volumes

    # by default directory-watcher it is disabled
    await _assert_enable_directory_watcher(client)

    assert mock_dir_watcher_on_any_event.call_count == 0

    json_outputs_labels = {
        k: v.dict(by_alias=True) for k, v in mock_outputs_labels.items()
    }
    response = await client.post(
        f"/{API_VTAG}/containers/ports/outputs/dirs",
        json={"outputs_labels": json_outputs_labels},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""

    for dir_name in mock_outputs_labels.keys():
        assert (mounted_volumes.disk_outputs_path / dir_name).is_dir()

    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == 2 * len(mock_outputs_labels)


async def test_container_pull_output_ports(
    client: TestClient, mock_port_keys: list[str], mock_nodeports: None
):
    response = await client.post(
        f"/{API_VTAG}/containers/ports/outputs:pull", json=mock_port_keys
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.text == "42"


async def test_container_push_output_ports(
    client: TestClient, mock_port_keys: list[str], mock_nodeports: None
):
    response = await client.post(
        f"/{API_VTAG}/containers/ports/outputs:push", json=mock_port_keys
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def test_container_push_output_ports_missing_node(
    client: TestClient,
    mock_port_keys: list[str],
    missing_node_uuid: str,
    mock_node_missing: None,
):
    response = await client.post(
        f"/{API_VTAG}/containers/ports/outputs:push", json=mock_port_keys
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    error_detail = response.json()
    assert error_detail["message"] == f"the node id {missing_node_uuid} was not found"
    assert error_detail["code"] == "dynamic_sidecar.nodeports.node_not_found"
    assert error_detail["node_uuid"] == missing_node_uuid


def _get_entrypoint_container_name(
    client: TestClient, dynamic_sidecar_network_name: str
) -> str:
    parsed_spec = parse_compose_spec(client.application.state.shared_store.compose_spec)
    container_name = None
    for service_name, service_details in parsed_spec["services"].items():
        if dynamic_sidecar_network_name in service_details.get("networks", []):
            container_name = service_name
            break
    assert container_name is not None
    return container_name


async def test_containers_entrypoint_name_ok(
    client: TestClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
):
    filters = json.dumps({"network": dynamic_sidecar_network_name})
    response = await client.get(f"/{API_VTAG}/containers/name?filters={filters}")
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == _get_entrypoint_container_name(
        client, dynamic_sidecar_network_name
    )


async def test_containers_entrypoint_name_containers_not_started(
    client: TestClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
):
    entrypoint_container = _get_entrypoint_container_name(
        client, dynamic_sidecar_network_name
    )

    # remove the container from the spec
    parsed_spec = parse_compose_spec(client.application.state.shared_store.compose_spec)
    del parsed_spec["services"][entrypoint_container]
    client.application.state.shared_store.compose_spec = yaml.safe_dump(parsed_spec)

    filters = json.dumps({"network": dynamic_sidecar_network_name})
    response = await client.get(f"/{API_VTAG}/containers/name?filters={filters}")
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert response.json() == {
        "detail": "No container found for network=entrypoint_container_network"
    }


async def test_containers_restart(client: TestClient, compose_spec: dict[str, Any]):
    # store spec first
    response = await client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": compose_spec}
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    shared_store: SharedStore = client.application.state.shared_store
    container_names = shared_store.container_names
    assert response.json() == container_names

    container_timestamps_before = await _get_container_timestamps(container_names)

    response = await client.post(
        f"/{API_VTAG}/containers:restart",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""

    container_timestamps_after = await _get_container_timestamps(container_names)

    for container_name in container_names:
        before: ContainerTimes = container_timestamps_before[container_name]
        after: ContainerTimes = container_timestamps_after[container_name]

        assert before.created == after.created
        assert before.started_at < after.started_at
        assert before.finished_at < after.finished_at


async def test_attach_detach_container_to_network(
    docker_swarm: None,
    client: TestClient,
    selected_spec: str,
    attachable_networks_and_ids: dict[str, str],
):
    response = await client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": selected_spec}
    )
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    shared_store: SharedStore = client.application.state.shared_store
    container_names = shared_store.container_names
    assert response.json() == container_names

    async with aiodocker.Docker() as docker:
        for container_name in container_names:
            for network_name, network_id in attachable_networks_and_ids.items():
                network_aliases = _create_network_aliases(network_name)

                # attach network to containers
                for _ in range(2):  # calling 2 times in a row
                    response = await client.post(
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
                assert set(networks[network_id]["Aliases"]) == set(network_aliases)

                # detach network from containers
                for _ in range(2):  # running twice in a row
                    response = await client.post(
                        f"/{API_VTAG}/containers/{container_name}/networks:detach",
                        json={"network_id": network_id},
                    )
                    assert (
                        response.status_code == status.HTTP_204_NO_CONTENT
                    ), response.text

                container = await docker.containers.get(container_name)
                container_inspect = await container.show()
                networks = container_inspect["NetworkSettings"]["Networks"]
                assert network_id in networks
