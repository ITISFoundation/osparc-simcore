# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import json
from typing import Any, Dict, List

import faker
import pytest
from async_asgi_testclient import TestClient
from fastapi import status
from pytest_mock.plugin import MockerFixture
from simcore_service_dynamic_sidecar._meta import api_vtag
from simcore_service_dynamic_sidecar.core.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.core.shared_handlers import (
    write_file_and_run_command,
)
from simcore_service_dynamic_sidecar.core.utils import async_command
from simcore_service_dynamic_sidecar.models.domains.shared_store import SharedStore

DEFAULT_COMMAND_TIMEOUT = 5.0

pytestmark = pytest.mark.asyncio

# FIXTURES


@pytest.fixture
def compose_spec() -> str:
    return json.dumps(
        {
            "version": "3",
            "services": {
                "first-box": {"image": "busybox"},
                "second-box": {"image": "busybox"},
            },
        }
    )


async def _docker_ps_a_container_names() -> List[str]:
    command = 'docker ps -a --format "{{.Names}}"'
    finished_without_errors, stdout = await async_command(
        command=command, command_timeout=None
    )

    assert finished_without_errors is True, stdout
    return stdout.split("\n")


async def assert_compose_spec_pulled(
    compose_spec: str, settings: DynamicSidecarSettings
) -> None:
    """ensures all containers inside compose_spec are pulled"""

    command = (
        "docker-compose --project-name {project} --file {file_path} "
        "up --no-build --detach"
    )
    finished_without_errors, stdout = await write_file_and_run_command(
        settings=settings,
        file_content=compose_spec,
        command=command,
        command_timeout=None,
    )

    assert finished_without_errors is True, stdout

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
async def started_containers(test_client: TestClient, compose_spec: str) -> List[str]:
    settings: DynamicSidecarSettings = test_client.application.state.settings
    await assert_compose_spec_pulled(compose_spec, settings)

    # start containers
    response = await test_client.post(f"/{api_vtag}/containers", data=compose_spec)
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text

    shared_store: SharedStore = test_client.application.state.shared_store
    container_names = shared_store.container_names
    assert len(container_names) == 2
    assert response.json() == container_names

    return container_names


@pytest.fixture
def not_started_containers() -> List[str]:
    return [f"missing-container-{i}" for i in range(5)]


@pytest.fixture
def mock_nodeports(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.nodeports.upload_outputs",
        return_value=None,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.nodeports.download_inputs",
        return_value=None,
    )


@pytest.fixture
def mock_data_manager(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.data_manager.upload_path_if_exists",
        return_value=None,
    )
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.data_manager.pull_path_if_exists",
        return_value=None,
    )
    from importlib import reload

    import simcore_service_dynamic_sidecar

    reload(simcore_service_dynamic_sidecar.api.containers)  # type: ignore


# TESTS


async def test_start_containers_wrong_spec(test_client: TestClient) -> None:
    response = await test_client.post(
        f"/{api_vtag}/containers", data={"opsie": "shame on me"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert response.json() == {"detail": "\nProvided yaml is not valid!"}


async def test_start_same_space_twice(
    test_client: TestClient, compose_spec: str
) -> None:
    settings: DynamicSidecarSettings = test_client.application.state.settings
    settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE = "test_name_space_1"
    await assert_compose_spec_pulled(compose_spec, settings)

    settings.DYNAMIC_SIDECAR_COMPOSE_NAMESPACE = "test_name_space_2"
    await assert_compose_spec_pulled(compose_spec, settings)


async def test_compose_up(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:

    response = await test_client.post(f"/{api_vtag}/containers", data=compose_spec)
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    shared_store: SharedStore = test_client.application.state.shared_store
    container_names = shared_store.container_names
    assert response.json() == container_names


async def test_compose_up_spec_not_provided(test_client: TestClient) -> None:
    response = await test_client.post(f"/{api_vtag}/containers")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert response.json() == {"detail": "\nProvided yaml is not valid!"}


async def test_compose_up_spec_invalid(test_client: TestClient) -> None:
    invalid_compose_spec = faker.Faker().text()  # pylint: disable=no-member
    response = await test_client.post(
        f"/{api_vtag}/containers", data=invalid_compose_spec
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert "Provided yaml is not valid!" in response.text
    # 28+ characters means the compos spec is also present in the error message
    assert len(response.text) > 28


async def test_containers_down_after_starting(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    # store spec first
    response = await test_client.post(f"/{api_vtag}/containers", data=compose_spec)
    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    shared_store: SharedStore = test_client.application.state.shared_store
    container_names = shared_store.container_names
    assert response.json() == container_names

    response = await test_client.post(
        f"/{api_vtag}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    assert response.text != ""


async def test_containers_down_missing_spec(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    response = await test_client.post(
        f"/{api_vtag}/containers:down",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, response.text
    assert response.json() == {"detail": "No spec for docker-compose down was found"}


def assert_keys_exist(result: Dict[str, Any]) -> bool:
    for entry in result.values():
        assert "Status" in entry
        assert "Error" in entry
    return True


async def test_containers_get(
    test_client: TestClient,
    started_containers: List[str],
    ensure_external_volumes: None,
) -> None:
    response = await test_client.get(f"/{api_vtag}/containers")
    assert response.status_code == status.HTTP_200_OK, response.text

    decoded_response = response.json()
    assert set(decoded_response) == set(started_containers)
    for entry in decoded_response.values():
        assert "Status" not in entry
        assert "Error" not in entry


async def test_containers_get_status(
    test_client: TestClient,
    started_containers: List[str],
    ensure_external_volumes: None,
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers", query_string=dict(only_status=True)
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    decoded_response = response.json()
    assert set(decoded_response) == set(started_containers)
    assert assert_keys_exist(decoded_response) is True


async def test_containers_inspect_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: int
) -> None:
    response = await test_client.get(f"/{api_vtag}/containers")
    assert response.status_code == mock_containers_get, response.text


async def test_containers_docker_status_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: int
) -> None:
    response = await test_client.get(f"/{api_vtag}/containers")
    assert response.status_code == mock_containers_get, response.text


async def test_container_inspect_logs_remove(
    test_client: TestClient, started_containers: List[str]
) -> None:
    for container in started_containers:
        # get container logs
        response = await test_client.get(f"/{api_vtag}/containers/{container}/logs")
        assert response.status_code == status.HTTP_200_OK, response.text

        # inspect container
        response = await test_client.get(f"/{api_vtag}/containers/{container}")
        assert response.status_code == status.HTTP_200_OK, response.text
        parsed_response = response.json()
        assert parsed_response["Name"] == f"/{container}"


async def test_container_logs_with_timestamps(
    test_client: TestClient, started_containers: List[str]
) -> None:
    for container in started_containers:
        # get container logs
        response = await test_client.get(
            f"/{api_vtag}/containers/{container}/logs",
            query_string=dict(timestamps=True),
        )
        assert response.status_code == status.HTTP_200_OK, response.text


async def test_container_missing_container(
    test_client: TestClient, not_started_containers: List[str]
) -> None:
    def _expected_error_string(container: str) -> Dict[str, str]:
        return dict(
            detail=f"No container '{container}' was started. Started containers '[]'"
        )

    for container in not_started_containers:
        # get container logs
        response = await test_client.get(f"/{api_vtag}/containers/{container}/logs")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert response.json() == _expected_error_string(container)

        # inspect container
        response = await test_client.get(f"/{api_vtag}/containers/{container}")
        assert response.status_code == status.HTTP_404_NOT_FOUND, response.text
        assert response.json() == _expected_error_string(container)


async def test_container_docker_error(
    test_client: TestClient,
    started_containers: List[str],
    mock_containers_get: int,
) -> None:
    def _expected_error_string() -> Dict[str, str]:
        return dict(detail="aiodocker_mocked_error")

    for container in started_containers:
        # get container logs
        response = await test_client.get(f"/{api_vtag}/containers/{container}/logs")
        assert response.status_code == mock_containers_get, response.text
        assert response.json() == _expected_error_string()

        # inspect container
        response = await test_client.get(f"/{api_vtag}/containers/{container}")
        assert response.status_code == mock_containers_get, response.text
        assert response.json() == _expected_error_string()


async def test_container_save_state(
    test_client: TestClient,
    mock_nodeports: None,
    mock_data_manager: None,
) -> None:
    response = await test_client.put(f"/{api_vtag}/containers:save-state")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""


async def test_container_restore_state(
    test_client: TestClient,
    mock_nodeports: None,
    mock_data_manager: None,
) -> None:
    response = await test_client.put(f"/{api_vtag}/containers:restore-state")
    assert response.status_code == status.HTTP_204_NO_CONTENT, response.text
    assert response.text == ""
