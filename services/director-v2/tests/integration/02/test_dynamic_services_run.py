# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
from typing import Dict, Callable
from uuid import uuid4

import pytest
import aiodocker
import sqlalchemy as sa
from yarl import URL
from httpx import AsyncClient
from models_library.projects import ProjectAtDB
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig


pytest_simcore_core_services_selection = [
    "director",
    "catalog",
    "director-v2",
    "redis",
    "rabbit",
    "postgres",
]
pytest_simcore_ops_services_selection = ["adminer"]

HTTPX_CLIENT_TIMOUT = 120


@pytest.fixture(autouse=True)
def minimal_configuration(
    httpbin_service: Dict,
    httpbin_dynamic_sidecar_service: Dict,
    httpbin_dynamic_sidecar_compose_service: Dict,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services: None,
):
    pass


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
async def httpbins_project(
    project: Callable,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    httpbin_service: Dict,
    httpbin_dynamic_sidecar_service: Dict,
    httpbin_dynamic_sidecar_compose_service: Dict,
    uuid_legacy: str,
    uuid_dynamic_sidecar: str,
    uuid_dynamic_sidecar_compose: str,
) -> ProjectAtDB:
    return project(
        workbench={
            uuid_legacy: {
                "key": httpbin_service["image"]["name"],
                "version": httpbin_service["image"]["tag"],
                "label": "legacy dynamic service",
            },
            uuid_dynamic_sidecar: {
                "key": httpbin_dynamic_sidecar_service["image"]["name"],
                "version": httpbin_dynamic_sidecar_service["image"]["tag"],
                "label": "dynamic sidecar",
            },
            uuid_dynamic_sidecar_compose: {
                "key": httpbin_dynamic_sidecar_compose_service["image"]["name"],
                "version": httpbin_dynamic_sidecar_compose_service["image"]["tag"],
                "label": "dynamic sidecar with docker compose spec",
            },
        }
    )


@pytest.fixture
async def director_v0_client(services_endpoint: Dict[str, URL]) -> AsyncClient:
    director_url = services_endpoint["director"]
    base_url = director_url / "v0"

    headers = {
        "X-Service-Sidecar-Request-DNS": director_url.host,
        "X-Service-Sidecar-Request-Scheme": director_url.scheme,
    }
    async with AsyncClient(
        base_url=str(base_url), headers=headers, timeout=HTTPX_CLIENT_TIMOUT
    ) as client:
        yield client


@pytest.fixture
async def director_v2_client(services_endpoint: Dict[str, URL]) -> AsyncClient:
    base_url = services_endpoint["director"] / "v2"
    async with AsyncClient(
        base_url=str(base_url), timeout=HTTPX_CLIENT_TIMOUT
    ) as client:
        yield client


@pytest.fixture(autouse=True)
async def ensure_services_stopped(httpbins_project: ProjectAtDB) -> None:
    yield
    # ensure service cleanup when done testing
    async with aiodocker.Docker() as docker_client:
        service_names = {x["Spec"]["Name"] for x in await docker_client.services.list()}
        # grep the names of the services
        for node_uuid in httpbins_project.workbench:
            for service_name in service_names:
                # if node_uuid is present in the service name it needs to be removed
                if node_uuid in service_name:
                    delete_result = await docker_client.services.delete(service_name)
                    assert delete_result is True


async def _assert_start_service(
    director_v0_client: AsyncClient,
    user_id: int,
    project_id: str,
    service_key: str,
    service_tag: str,
    service_uuid: str,
) -> None:
    query_params = dict(
        user_id=user_id,
        project_id=project_id,
        service_key=service_key,
        service_tag=service_tag,
        service_uuid=service_uuid,
    )
    result = await director_v0_client.post(
        "/running_interactive_services", params=query_params
    )
    assert result.status_code == 201, result.text
    assert "data" in result.json()


async def _assert_stop_service(
    director_v0_client: AsyncClient, service_uuid: str
) -> None:
    result = await director_v0_client.delete(
        "/running_interactive_services", params=dict(service_uuid=service_uuid)
    )
    assert result.status_code == 200
    assert result.text == ""


async def test_legacy_and_dynamic_sidecar_run(
    # client: TestClient,
    httpbins_project: ProjectAtDB,
    user_db: Dict,
    director_v0_client: AsyncClient,
    director_v2_client: AsyncClient,
):
    """
    The test will start 3 dynamic services in the same project and check
    that the legacy and the 2 new dynamic-sidecar boot properly.

    Creates a project containing the following services:
    - httpbin
    - httpbin-dynamic-sidecar
    - httpbin-dynamic-sidecar-compose
    """

    services_to_start = []
    for service_uuid, node in httpbins_project.workbench.items():
        services_to_start.append(
            _assert_start_service(
                director_v0_client=director_v0_client,
                user_id=user_db["id"],
                project_id=httpbins_project.uuid,
                service_key=node.key,
                service_tag=node.version,
                service_uuid=service_uuid,
            )
        )
    await asyncio.gather(*services_to_start)

    services_to_stop = []
    for service_uuid in httpbins_project.workbench:
        services_to_stop.append(
            _assert_stop_service(
                director_v0_client=director_v0_client, service_uuid=service_uuid
            )
        )
    await asyncio.gather(*services_to_stop)
