# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from typing import Any, Dict, List

import pytest
from async_asgi_testclient import TestClient
from simcore_service_dynamic_sidecar._meta import api_vtag
from simcore_service_dynamic_sidecar.storage import SharedStore


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
    container_names = shared_store.get_container_names()
    assert len(container_names) == 2

    return container_names


@pytest.fixture
def not_started_containers() -> List[str]:
    return [f"missing-container-{i}" for i in range(5)]


@pytest.mark.asyncio
async def test_container_inspect_logs_remove(
    test_client: TestClient, started_containers: List[str]
):
    for container in started_containers:
        # get container logs
        response = await test_client.get(
            f"/{api_vtag}/container/logs", query_string=dict(container=container)
        )
        assert response.status_code == 200, response.text

        # inspect container
        response = await test_client.get(
            f"/{api_vtag}/container/inspect", query_string=dict(container=container)
        )
        assert response.status_code == 200, response.text
        parsed_response = response.json()
        assert parsed_response["Name"] == f"/{container}"

        # delete container
        response = await test_client.delete(
            f"/{api_vtag}/container/remove", query_string=dict(container=container)
        )
        assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_container_logs_with_timestamps(
    test_client: TestClient, started_containers: List[str]
):
    for container in started_containers:
        # get container logs
        response = await test_client.get(
            f"/{api_vtag}/container/logs",
            query_string=dict(container=container, timestamps=True),
        )
        assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_container_missing_container(
    test_client: TestClient, not_started_containers: List[str]
):
    def _expected_error_string(container: str) -> Dict[str, str]:
        return dict(error=f"No container '{container}' was started")

    for container in not_started_containers:
        # get container logs
        response = await test_client.get(
            f"/{api_vtag}/container/logs", query_string=dict(container=container)
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string(container)

        # inspect container
        response = await test_client.get(
            f"/{api_vtag}/container/inspect", query_string=dict(container=container)
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string(container)

        # delete container
        response = await test_client.delete(
            f"/{api_vtag}/container/remove", query_string=dict(container=container)
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string(container)


@pytest.mark.asyncio
async def test_container_docker_error(
    test_client: TestClient,
    started_containers: List[str],
    mock_containers_get: None,
):
    def _expected_error_string() -> Dict[str, str]:
        return dict(error="aiodocker_mocked_error")

    for container in started_containers:
        # get container logs
        response = await test_client.get(
            f"/{api_vtag}/container/logs", query_string=dict(container=container)
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string()

        # inspect container
        response = await test_client.get(
            f"/{api_vtag}/container/inspect", query_string=dict(container=container)
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string()

        # delete container
        response = await test_client.delete(
            f"/{api_vtag}/container/remove", query_string=dict(container=container)
        )
        assert response.status_code == 400, response.text
        assert response.json() == _expected_error_string()
