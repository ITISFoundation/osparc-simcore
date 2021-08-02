# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

import aiodocker
import httpx
import pytest
import sqlalchemy as sa
import tenacity
from async_timeout import timeout
from models_library.projects import Node, ProjectAtDB
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pydantic.types import PositiveInt
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
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

# FIXTURES


@pytest.fixture
def minimal_configuration(
    dy_static_file_server_service: Dict,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: Dict,
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
async def dy_static_file_server_project(
    minimal_configuration: None,
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


# UTILS


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


def _is_legacy(node_data: Node) -> bool:
    return node_data.label == "LEGACY"


async def _get_service_data(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    service_uuid: str,
    node_data: Node,
) -> Dict[str, Any]:
    result = await director_v2_client.get(
        f"/dynamic_services/{service_uuid}", allow_redirects=False
    )
    result = await _handle_307_if_required(director_v2_client, director_v0_url, result)
    assert result.status_code == 200, result.text

    payload = result.json()
    data = payload["data"] if _is_legacy(node_data) else payload
    return data


async def _get_service_state(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    service_uuid: str,
    node_data: Node,
) -> str:
    data = await _get_service_data(
        director_v2_client, director_v0_url, service_uuid, node_data
    )
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


async def _run_command(command: str) -> str:
    """Runs a command and expects to"""
    proc = await asyncio.create_subprocess_shell(
        command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    stdout, _ = await proc.communicate()
    decoded_stdout = stdout.decode()
    print(f"'{command}' result:\n{decoded_stdout}")
    assert proc.returncode == 0, decoded_stdout

    return decoded_stdout


async def _port_forward_service(
    service_name: str, is_legacy: bool, internal_port: PositiveInt
) -> PositiveInt:
    """Updates the service configuration and makes it so it can be used"""
    # By updating the service spec the container will be recreated.
    # It works in this case, since we do not care about the internal
    # state of the application
    target_service = service_name

    if is_legacy:
        # Legacy services are started --endpoint-mode dnsrr, it needs to
        # be changed to vip otherwise the port forward will not work
        await _run_command(f"docker service update {service_name} --endpoint-mode=vip")
    else:
        # For a non legacy service, the service_name points to the dynamic-sidecar,
        # but traffic is handeled by the proxy,
        target_service = service_name.replace(
            DYNAMIC_SIDECAR_SERVICE_PREFIX, DYNAMIC_PROXY_SERVICE_PREFIX
        )

    # Finally forward the port on a random assigned port.
    await _run_command(
        f"docker service update {target_service} --publish-add :{internal_port}"
    )

    # inspect service and fetch the port
    async with aiodocker.Docker() as docker_client:
        service_details = await docker_client.services.inspect(target_service)
        ports = service_details["Endpoint"]["Ports"]

        assert len(ports) == 1, service_details
        exposed_port = ports[0]["PublishedPort"]
        return exposed_port


async def _assert_service_is_available(exposed_port: PositiveInt) -> None:
    service_address = f"http://localhost:{exposed_port}"
    print(f"checking service @ {service_address}")

    async for attempt in tenacity.AsyncRetrying(
        wait=tenacity.wait_exponential(), stop=tenacity.stop_after_delay(10)
    ):
        with attempt:
            async with httpx.AsyncClient() as client:
                response = await client.get(service_address)
                assert response.status_code == 200


# TESTS


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

    # query the service directly and check if it responding accordingly
    for (
        dynamic_service_uuid,
        node_data,
    ) in dy_static_file_server_project.workbench.items():
        service_data = await _get_service_data(
            director_v2_client=director_v2_client,
            director_v0_url=director_v0_url,
            service_uuid=dynamic_service_uuid,
            node_data=node_data,
        )
        print(
            "Checking running service availability",
            dynamic_service_uuid,
            node_data,
            service_data,
        )
        exposed_port = await _port_forward_service(
            service_name=service_data["service_host"],
            is_legacy=_is_legacy(node_data),
            internal_port=service_data["service_port"],
        )

        await _assert_service_is_available(exposed_port)

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
