# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument


import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List

import pytest
from async_asgi_testclient import TestClient
from faker import Faker
from fastapi import status
from simcore_service_dynamic_sidecar._meta import api_vtag
from simcore_service_dynamic_sidecar.settings import DynamicSidecarSettings
from simcore_service_dynamic_sidecar.shared_handlers import write_file_and_run_command
from simcore_service_dynamic_sidecar.shared_store import SharedStore

DEFAULT_COMMAND_TIMEOUT = 10.0

pytestmark = pytest.mark.asyncio


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
        command_timeout=10.0,
    )

    assert finished_without_errors is True, stdout


@pytest.fixture
async def started_containers(test_client: TestClient, compose_spec: str) -> List[str]:
    settings: DynamicSidecarSettings = test_client.application.state.settings
    await assert_compose_spec_pulled(compose_spec, settings)

    # start containers
    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=10.0),
        data=compose_spec,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert json.loads(response.text) is None

    shared_store: SharedStore = test_client.application.state.shared_store
    container_names = shared_store.container_names
    assert len(container_names) == 2

    return container_names


@pytest.fixture
def not_started_containers() -> List[str]:
    return [f"missing-container-{i}" for i in range(5)]


async def test_compose_up(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:

    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=compose_spec,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert json.loads(response.text) is None


async def test_compose_up_spec_not_provided(test_client: TestClient) -> None:
    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert json.loads(response.text) == {"detail": "\nProvided yaml is not valid!"}


async def test_compose_up_spec_invalid(test_client: TestClient) -> None:
    invalid_compose_spec = Faker().text()
    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=invalid_compose_spec,
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert "Provided yaml is not valid!" in response.text
    # 28+ characters means the compos spec is also present in the error message
    assert len(response.text) > 28


async def test_containers_down_after_starting(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> None:
    # store spec first
    response = await test_client.post(
        f"/{api_vtag}/containers",
        query_string=dict(command_timeout=DEFAULT_COMMAND_TIMEOUT),
        data=compose_spec,
    )
    assert response.status_code == status.HTTP_201_CREATED, response.text
    assert json.loads(response.text) is None

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
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text
    assert json.loads(response.text) == {
        "detail": "No spec for docker-compose down was found"
    }


def assert_keys_exist(result: Dict[str, Any]) -> bool:
    for entry in result.values():
        assert "Status" in entry
        assert "Error" in entry
    return True


async def test_containers_get(
    test_client: TestClient, started_containers: List[str]
) -> None:
    response = await test_client.get(f"/{api_vtag}/containers")
    assert response.status_code == status.HTTP_200_OK, response.text

    decoded_response = json.loads(response.text)
    assert set(decoded_response) == set(started_containers)
    for entry in decoded_response.values():
        assert "Status" not in entry
        assert "Error" not in entry


async def test_containers_get_status(
    test_client: TestClient, started_containers: List[str]
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers", query_string=dict(only_status=True)
    )
    assert response.status_code == status.HTTP_200_OK, response.text

    decoded_response = json.loads(response.text)
    assert set(decoded_response) == set(started_containers)
    assert assert_keys_exist(decoded_response) is True


async def test_containers_inspect_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: None
) -> None:
    response = await test_client.get(f"/{api_vtag}/containers")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text


async def test_containers_docker_status_pulling_containers(
    test_client: TestClient, started_containers: List[str]
) -> None:
    @contextmanager
    def mark_pulling(shared_store: SharedStore) -> Generator[None, None, None]:
        try:
            shared_store.is_pulling_containers = True
            yield
        finally:
            shared_store.is_pulling_containers = False

    shared_store: SharedStore = test_client.application.state.shared_store

    with mark_pulling(shared_store):
        assert shared_store.is_pulling_containers is True

        response = await test_client.get(f"/{api_vtag}/containers")
        assert response.status_code == status.HTTP_200_OK, response.text
        decoded_response = json.loads(response.text)
        assert assert_keys_exist(decoded_response) is True

        for entry in decoded_response.values():
            assert entry["Status"] == "pulling"


async def test_containers_docker_status_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: None
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR, response.text


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
    mock_containers_get: None,
) -> None:
    def _expected_error_string() -> Dict[str, str]:
        return dict(detail="aiodocker_mocked_error")

    for container in started_containers:
        # get container logs
        response = await test_client.get(f"/{api_vtag}/containers/{container}/logs")
        assert (
            response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        ), response.text
        assert response.json() == _expected_error_string()

        # inspect container
        response = await test_client.get(f"/{api_vtag}/containers/{container}")
        assert (
            response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        ), response.text
        assert response.json() == _expected_error_string()
