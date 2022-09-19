# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import json
import random
from inspect import signature
from pathlib import Path
from typing import Any, AsyncIterable, Final, Iterator
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import aiodocker
import pytest
import yaml
from aiodocker.volumes import DockerVolume
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import FastAPI, status
from models_library.services import ServiceOutput
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from servicelib.fastapi.long_running_tasks.client import TaskId
from simcore_service_dynamic_sidecar._meta import API_VTAG
from simcore_service_dynamic_sidecar.core.application import AppState
from simcore_service_dynamic_sidecar.core.docker_compose_utils import (
    docker_compose_create,
)
from simcore_service_dynamic_sidecar.core.settings import ApplicationSettings
from simcore_service_dynamic_sidecar.core.utils import HIDDEN_FILE_NAME, async_command
from simcore_service_dynamic_sidecar.core.validation import parse_compose_spec
from simcore_service_dynamic_sidecar.models.shared_store import SharedStore
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

WAIT_FOR_DIRECTORY_WATCHER: Final[float] = 0.1
FAST_POLLING_INTERVAL: Final[float] = 0.1

# UTILS


def _create_network_aliases(network_name: str) -> list[str]:
    return [f"alias_{i}_{network_name}" for i in range(10)]


async def _assert_enable_directory_watcher(test_client: TestClient) -> None:
    response = await test_client.patch(
        f"/{API_VTAG}/containers/directory-watcher", json=dict(is_enabled=True)
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def _assert_disable_directory_watcher(test_client: TestClient) -> None:
    response = await test_client.patch(
        f"/{API_VTAG}/containers/directory-watcher", json=dict(is_enabled=False)
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def _start_containers(test_client: TestClient, compose_spec: str) -> list[str]:
    # start containers
    response = await test_client.post(
        f"/{API_VTAG}/containers", json={"docker_compose_yaml": compose_spec}
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
                raise RuntimeError(f"Waiting for task to complete, got: {task_status}")

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
def app(app: FastAPI) -> FastAPI:
    app.state.shared_store = SharedStore()  # emulate on_startup event
    return app


@pytest.fixture
def test_client(
    ensure_shared_store_dir: Path,
    ensure_run_in_sequence_context_is_empty: None,
    ensure_external_volumes: tuple[DockerVolume],
    cleanup_containers,
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


@pytest.fixture
async def started_containers(test_client: TestClient, compose_spec: str) -> list[str]:
    settings: ApplicationSettings = test_client.application.state.settings
    await _assert_compose_spec_pulled(compose_spec, settings)

    return await _start_containers(test_client, compose_spec)


@pytest.fixture
def not_started_containers() -> list[str]:
    return [f"missing-container-{i}" for i in range(5)]


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
def mock_aiodocker_containers_get(mocker: MockerFixture) -> int:
    """raises a DockerError with a random HTTP status which is also returned"""
    mock_status_code = random.randint(1, 999)

    async def mock_get(*args: str, **kwargs: Any) -> None:
        raise aiodocker.exceptions.DockerError(
            status=mock_status_code, data=dict(message="aiodocker_mocked_error")
        )

    mocker.patch("aiodocker.containers.DockerContainers.get", side_effect=mock_get)

    return mock_status_code


@pytest.fixture
def mock_dir_watcher_on_any_event(
    app: FastAPI, monkeypatch: MonkeyPatch
) -> Iterator[Mock]:

    mock = Mock(return_value=None)

    monkeypatch.setattr(
        app.state.dir_watcher.outputs_event_handle, "_invoke_push_directory", mock
    )
    yield mock


def test_ensure_api_vtag_is_v1():
    assert API_VTAG == "v1"


async def test_start_same_space_twice(compose_spec: str, test_client: TestClient):
    settings = test_client.application.state.settings

    settings_1 = settings.copy(
        update={"DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": "test_name_space_1"}, deep=True
    )
    await _assert_compose_spec_pulled(compose_spec, settings_1)

    settings_2 = settings.copy(
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
            query_string=dict(timestamps=True),
        )
        assert response.status_code == status.HTTP_200_OK, response.text
        assert response.json() == []


async def test_container_missing_container(
    test_client: TestClient, not_started_containers: list[str]
):
    def _expected_error_string(container: str) -> dict[str, str]:
        return dict(
            detail=f"No container '{container}' was started. Started containers '[]'"
        )

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
                f"An unexpected Docker error occurred status={status_code}, message='aiodocker_mocked_error'"
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


async def test_directory_watcher_disabling(
    test_client: TestClient,
    mock_dir_watcher_on_any_event: AsyncMock,
):
    assert isinstance(test_client.application, FastAPI)
    mounted_volumes = AppState(test_client.application).mounted_volumes

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
    await _assert_enable_directory_watcher(test_client)
    assert mock_dir_watcher_on_any_event.call_count == 0
    dir_count = _create_random_dir_in_inputs()
    assert dir_count == 1
    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == EVENTS_PER_DIR_CREATION

    # disable and wait for events should have the same count as before
    await _assert_disable_directory_watcher(test_client)
    dir_count = _create_random_dir_in_inputs()
    assert dir_count == 2
    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == EVENTS_PER_DIR_CREATION

    # enable and wait for events
    await _assert_enable_directory_watcher(test_client)
    dir_count = _create_random_dir_in_inputs()
    assert dir_count == 3
    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == 2 * EVENTS_PER_DIR_CREATION


async def test_container_create_outputs_dirs(
    test_client: TestClient,
    mock_outputs_labels: dict[str, ServiceOutput],
    mock_dir_watcher_on_any_event: AsyncMock,
):
    assert isinstance(test_client.application, FastAPI)
    mounted_volumes = AppState(test_client.application).mounted_volumes

    # by default directory-watcher it is disabled
    await _assert_enable_directory_watcher(test_client)

    assert mock_dir_watcher_on_any_event.call_count == 0

    json_outputs_labels = {
        k: v.dict(by_alias=True) for k, v in mock_outputs_labels.items()
    }
    response = await test_client.post(
        f"/{API_VTAG}/containers/ports/outputs/dirs",
        json={"outputs_labels": json_outputs_labels},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""

    for dir_name in mock_outputs_labels.keys():
        assert (mounted_volumes.disk_outputs_path / dir_name).is_dir()

    await asyncio.sleep(WAIT_FOR_DIRECTORY_WATCHER)
    assert mock_dir_watcher_on_any_event.call_count == 2 * len(mock_outputs_labels)


def _get_entrypoint_container_name(
    test_client: TestClient, dynamic_sidecar_network_name: str
) -> str:
    parsed_spec = parse_compose_spec(
        test_client.application.state.shared_store.compose_spec
    )
    container_name = None
    for service_name, service_details in parsed_spec["services"].items():
        if dynamic_sidecar_network_name in service_details.get("networks", []):
            container_name = service_name
            break
    assert container_name is not None
    return container_name


async def test_containers_entrypoint_name_ok(
    test_client: TestClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
):
    filters = json.dumps({"network": dynamic_sidecar_network_name})
    response = await test_client.get(f"/{API_VTAG}/containers/name?filters={filters}")
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.json() == _get_entrypoint_container_name(
        test_client, dynamic_sidecar_network_name
    )


async def test_containers_entrypoint_name_containers_not_started(
    test_client: TestClient,
    dynamic_sidecar_network_name: str,
    started_containers: list[str],
):
    entrypoint_container = _get_entrypoint_container_name(
        test_client, dynamic_sidecar_network_name
    )

    # remove the container from the spec
    parsed_spec = parse_compose_spec(
        test_client.application.state.shared_store.compose_spec
    )
    del parsed_spec["services"][entrypoint_container]
    test_client.application.state.shared_store.compose_spec = yaml.safe_dump(
        parsed_spec
    )

    filters = json.dumps({"network": dynamic_sidecar_network_name})
    response = await test_client.get(f"/{API_VTAG}/containers/name?filters={filters}")
    assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
    assert response.json() == {
        "detail": "No container found for network=entrypoint_container_network"
    }


async def test_attach_detach_container_to_network(
    docker_swarm: None,
    test_client: TestClient,
    selected_spec: str,
    attachable_networks_and_ids: dict[str, str],
):
    container_names = await _start_containers(test_client, selected_spec)

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
                assert set(networks[network_id]["Aliases"]) == set(network_aliases)

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
                assert network_id in networks
