# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
from typing import Callable, Dict, Optional
from uuid import uuid4

import aiodocker
import httpx
import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from async_timeout import timeout
from models_library.projects import Node, ProjectAtDB
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
    "catalog",
    "director",
    "director-v2",
]

HTTPX_CLIENT_TIMOUT = 10
SERVICES_ARE_READY_TIMEOUT = 10 * 60


@pytest.fixture(autouse=True)
def minimal_configuration(
    dy_static_file_server_service: Dict,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: Dict,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services: None,
    monkeypatch: MonkeyPatch,
):
    monkeypatch.setenv(
        "DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:TEST_MOCKED_TAG_NOT_PRESENT"
    )
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_services_network_name")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_mocked_simcore_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_mocked_stack_name")


def _str_uuid() -> str:
    return str(uuid4())


@pytest.fixture
def uuid_legacy() -> str:
    return _str_uuid()


@pytest.fixture
def uuid_dynamic_sidecar() -> str:
    return _str_uuid()


@pytest.fixture
def uuid_dynamic_sidecar_compose() -> str:
    return _str_uuid()


@pytest.fixture
async def dy_static_file_server_project(
    project: Callable,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    dy_static_file_server_service: Dict,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: Dict,
    uuid_legacy: str,
    uuid_dynamic_sidecar: str,
    uuid_dynamic_sidecar_compose: str,
) -> ProjectAtDB:
    def _assemble_node_data(spec: Dict, label: str) -> Dict[str, str]:
        return {
            "key": spec["image"]["name"],
            "version": spec["image"]["tag"],
            "label": label,
        }

    return project(
        workbench={
            uuid_legacy: _assemble_node_data(
                dy_static_file_server_service,
                "LEGACY",
            ),
            uuid_dynamic_sidecar: _assemble_node_data(
                dy_static_file_server_dynamic_sidecar_service,
                "DYNAMIC",
            ),
            uuid_dynamic_sidecar_compose: _assemble_node_data(
                dy_static_file_server_dynamic_sidecar_compose_spec_service,
                "DYNAMIC_COMPOSE",
            ),
        }
    )


@pytest.fixture
async def director_v2_client(services_endpoint: Dict[str, URL]) -> httpx.AsyncClient:
    base_url = services_endpoint["director-v2"] / "v2"
    async with httpx.AsyncClient(
        base_url=str(base_url), timeout=HTTPX_CLIENT_TIMOUT
    ) as client:
        yield client


@pytest.fixture(autouse=True)
async def ensure_services_stopped(dy_static_file_server_project: ProjectAtDB) -> None:
    yield
    # ensure service cleanup when done testing
    async with aiodocker.Docker() as docker_client:
        service_names = {x["Spec"]["Name"] for x in await docker_client.services.list()}

        # grep the names of the services
        for node_uuid in dy_static_file_server_project.workbench:
            for service_name in service_names:
                # if node_uuid is present in the service name it needs to be removed
                if node_uuid in service_name:
                    delete_result = await docker_client.services.delete(service_name)
                    assert delete_result is True


async def _handle_307_if_required(
    director_v2_client: httpx.AsyncClient, director_v0_url: URL, result: httpx.Response
) -> httpx.Response:
    if result.next_request is not None:
        # replace url endpoint for director-v0 in redirect
        print("REDIRECTING[1/3]", result, result.headers, result.text)
        result.next_request.url = httpx.URL(
            str(result.next_request.url).replace(
                "http://director:8080", str(director_v0_url)
            )
        )
        print("REDIRECTING[2/3]", result.next_request.url)
        result = await director_v2_client.send(result.next_request)
        print("REDIRECTING[3/3]", result, result.headers, result.text)
    return result


async def _assert_start_service(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    user_id: int,
    project_id: str,
    service_key: str,
    service_version: str,
    service_uuid: str,
    basepath: Optional[str],
) -> None:
    data = dict(
        user_id=user_id,
        project_id=project_id,
        service_key=service_key,
        service_version=service_version,
        service_uuid=service_uuid,
        basepath=basepath,
    )
    headers = {
        "x-dynamic-sidecar-request-dns": director_v2_client.base_url.host,
        "x-dynamic-sidecar-request-scheme": director_v2_client.base_url.scheme,
    }

    result = await director_v2_client.post(
        "/dynamic_services", json=data, headers=headers, allow_redirects=False
    )
    result = await _handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 201, result.text


async def _get_service_state(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    service_uuid: str,
    node_data: Node,
) -> str:
    result = await director_v2_client.get(
        f"/dynamic_services/{service_uuid}", allow_redirects=False
    )
    result = await _handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 200, result.text

    payload = result.json()
    data = payload["data"] if node_data.label == "LEGACY" else payload
    print("STATUS_RESULT", node_data.label, data["service_state"])
    return data["service_state"]


async def _assert_stop_service(
    director_v2_client: httpx.AsyncClient, director_v0_url: URL, service_uuid: str
) -> None:
    result = await director_v2_client.delete(
        f"/dynamic_services/{service_uuid}", allow_redirects=False
    )
    result = await _handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 204
    assert result.text == ""


async def test_legacy_and_dynamic_sidecar_run(
    dy_static_file_server_project: ProjectAtDB,
    user_db: Dict,
    services_endpoint: Dict[str, URL],
    director_v2_client: httpx.AsyncClient,
):
    """
    The test will start 3 dynamic services in the same project and check
    that the legacy and the 2 new dynamic-sidecar boot properly.

    Creates a project containing the following services:
    - dy-static-file-server
    - dy-static-file-server-dynamic-sidecar
    - dy-static-file-server-dynamic-sidecar-compose
    """
    director_v0_url = services_endpoint["director"]

    services_to_start = []
    for service_uuid, node in dy_static_file_server_project.workbench.items():
        services_to_start.append(
            _assert_start_service(
                director_v2_client=director_v2_client,
                director_v0_url=director_v0_url,
                user_id=user_db["id"],
                project_id=str(dy_static_file_server_project.uuid),
                service_key=node.key,
                service_version=node.version,
                service_uuid=service_uuid,
                basepath=f"/x/{service_uuid}" if node.label == "LEGACY" else None,
            )
        )
    await asyncio.gather(*services_to_start)

    assert len(dy_static_file_server_project.workbench) == 3

    async with timeout(SERVICES_ARE_READY_TIMEOUT):
        not_all_services_running = True

        while not_all_services_running:
            service_states = [
                _get_service_state(
                    director_v2_client=director_v2_client,
                    director_v0_url=director_v0_url,
                    service_uuid=dynamic_service_uuid,
                    node_data=node_data,
                )
                for dynamic_service_uuid, node_data in dy_static_file_server_project.workbench.items()
            ]
            are_services_running = [
                x == "running" for x in await asyncio.gather(*service_states)
            ]
            not_all_services_running = not all(are_services_running)
            # let the services boot
            await asyncio.sleep(1.0)

    # finally stop the started services
    services_to_stop = []
    for service_uuid in dy_static_file_server_project.workbench:
        services_to_stop.append(
            _assert_stop_service(
                director_v2_client=director_v2_client,
                director_v0_url=director_v0_url,
                service_uuid=service_uuid,
            )
        )
    await asyncio.gather(*services_to_stop)
