# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List

import pytest
from async_asgi_testclient import TestClient
from simcore_service_dynamic_sidecar._meta import api_vtag
from simcore_service_dynamic_sidecar.shared_store import SharedStore

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


@pytest.fixture
async def started_containers(
    test_client: TestClient, compose_spec: Dict[str, Any]
) -> List[str]:
    # store spec first
    response = await test_client.post(f"/{api_vtag}/compose:store", data=compose_spec)
    assert response.status_code == 204, response.text
    assert response.text == ""

    # pull images for spec
    response = await test_client.post(
        f"/{api_vtag}/compose", query_string=dict(command_timeout=10.0)
    )
    assert response.status_code == 200, response.text

    shared_store: SharedStore = test_client.application.state.shared_store
    container_names = shared_store.container_names
    assert len(container_names) == 2

    return container_names


@pytest.fixture
def not_started_containers() -> List[str]:
    return [f"missing-container-{i}" for i in range(5)]


async def test_containers_get(
    test_client: TestClient, started_containers: List[str]
) -> None:
    response = await test_client.get(f"/{api_vtag}/containers")
    assert response.status_code == 200, response.text
    assert set(json.loads(response.text)) == set(started_containers)


async def test_containers_inspect(
    test_client: TestClient, started_containers: List[str]
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers:inspect",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == 200, response.text
    assert set(json.loads(response.text).keys()) == set(started_containers)


async def test_containers_inspect_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: None
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers:inspect",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == 400, response.text


def assert_keys_exist(result: Dict[str, Any]) -> bool:
    for entry in result.values():
        assert "Status" in entry
        assert "Error" in entry
    return True


async def test_containers_docker_status(
    test_client: TestClient, started_containers: List[str]
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers:docker-status",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == 200, response.text
    decoded_response = json.loads(response.text)
    assert set(decoded_response) == set(started_containers)
    assert assert_keys_exist(decoded_response) is True


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

        response = await test_client.get(
            f"/{api_vtag}/containers:docker-status",
            query_string=dict(container_names=started_containers),
        )
        assert response.status_code == 200, response.text
        decoded_response = json.loads(response.text)
        assert assert_keys_exist(decoded_response) is True

        for entry in decoded_response.values():
            assert entry["Status"] == "pulling"


async def test_containers_docker_status_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: None
) -> None:
    response = await test_client.get(
        f"/{api_vtag}/containers:docker-status",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == 400, response.text


async def test_container_inspect_logs_remove(
    test_client: TestClient, started_containers: List[str]
) -> None:
    for container in started_containers:
        # get container logs
        response = await test_client.get(f"/{api_vtag}/containers/{container}/logs")
        assert response.status_code == 200, response.text

        # inspect container
        response = await test_client.get(f"/{api_vtag}/containers/{container}/inspect")
        assert response.status_code == 200, response.text
        parsed_response = response.json()
        assert parsed_response["Name"] == f"/{container}"

        # delete container
        response = await test_client.delete(
            f"/{api_vtag}/containers/{container}/remove"
        )
        assert response.status_code == 200, response.text


async def test_container_logs_with_timestamps(
    test_client: TestClient, started_containers: List[str]
) -> None:
    for container in started_containers:
        # get container logs
        response = await test_client.get(
            f"/{api_vtag}/containers/{container}/logs",
            query_string=dict(timestamps=True),
        )
        assert response.status_code == 200, response.text


async def test_container_missing_container(
    test_client: TestClient, not_started_containers: List[str]
) -> None:
    def _expected_error_string(container: str) -> Dict[str, str]:
        return dict(error=f"No container '{container}' was started")

    for container in not_started_containers:
        # get container logs
        response = await test_client.get(f"/{api_vtag}/containers/{container}/logs")
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string(container)

        # inspect container
        response = await test_client.get(f"/{api_vtag}/containers/{container}/inspect")
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string(container)

        # delete container
        response = await test_client.delete(
            f"/{api_vtag}/containers/{container}/remove"
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string(container)


async def test_container_docker_error(
    test_client: TestClient,
    started_containers: List[str],
    mock_containers_get: None,
) -> None:
    def _expected_error_string() -> Dict[str, str]:
        return dict(error="aiodocker_mocked_error")

    for container in started_containers:
        # get container logs
        response = await test_client.get(f"/{api_vtag}/containers/{container}/logs")
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string()

        # inspect container
        response = await test_client.get(f"/{api_vtag}/containers/{container}/inspect")
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string()

        # delete container
        response = await test_client.delete(
            f"/{api_vtag}/containers/{container}/remove"
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string()
