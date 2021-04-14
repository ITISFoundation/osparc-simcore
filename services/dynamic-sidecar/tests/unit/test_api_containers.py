# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List

import pytest
from async_asgi_testclient import TestClient
from simcore_service_dynamic_sidecar.storage import SharedStore
from simcore_service_dynamic_sidecar._meta import api_vtag


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


@pytest.mark.asyncio
async def test_containers_get(test_client: TestClient, started_containers: List[str]):
    response = await test_client.get(f"/{api_vtag}/containers")
    assert response.status_code == 200, response.text
    assert set(json.loads(response.text)) == set(started_containers)


@pytest.mark.asyncio
async def test_containers_inspect(
    test_client: TestClient, started_containers: List[str]
):
    response = await test_client.get(
        f"/{api_vtag}/containers:inspect",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == 200, response.text
    assert set(json.loads(response.text).keys()) == set(started_containers)


@pytest.mark.asyncio
async def test_containers_inspect_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: None
):
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


@pytest.mark.asyncio
async def test_containers_docker_status(
    test_client: TestClient, started_containers: List[str]
):
    response = await test_client.get(
        f"/{api_vtag}/containers:docker-status",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == 200, response.text
    decoded_response = json.loads(response.text)
    assert set(decoded_response) == set(started_containers)
    assert assert_keys_exist(decoded_response) is True


@pytest.mark.asyncio
async def test_containers_docker_status_pulling_containers(
    test_client: TestClient, started_containers: List[str]
):
    @contextmanager
    def mark_pulling(shared_store: SharedStore) -> Generator[None, None, None]:
        try:
            shared_store.set_is_pulling_containsers()
            yield
        finally:
            shared_store.unset_is_pulling_containsers()

    shared_store: SharedStore = test_client.application.state.shared_store

    with mark_pulling(shared_store):
        assert shared_store.is_pulling_containsers is True

        response = await test_client.get(
            f"/{api_vtag}/containers:docker-status",
            query_string=dict(container_names=started_containers),
        )
        assert response.status_code == 200, response.text
        decoded_response = json.loads(response.text)
        assert assert_keys_exist(decoded_response) is True

        for entry in decoded_response.values():
            assert entry["Status"] == "pulling"


@pytest.mark.asyncio
async def test_containers_docker_status_docker_error(
    test_client: TestClient, started_containers: List[str], mock_containers_get: None
):
    response = await test_client.get(
        f"/{api_vtag}/containers:docker-status",
        query_string=dict(container_names=started_containers),
    )
    assert response.status_code == 400, response.text
