# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
import os
from typing import Any, Callable, Dict, Optional, Union
from uuid import uuid4

import aiodocker
import httpx
import pytest
import requests
import sqlalchemy as sa
import tenacity
from asgi_lifespan import LifespanManager
from async_timeout import timeout
from models_library.projects import Node, ProjectAtDB
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pydantic.types import PositiveInt
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from utils import ensure_network_cleanup, patch_dynamic_service_url
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
    "redis",
    "rabbit",
    "catalog",
    "director",
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
    ensure_swarm_and_networks: None,
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
async def director_v2_client(
    minimal_configuration: None,
    loop: asyncio.BaseEventLoop,
    mock_env: None,
    network_name: str,
    monkeypatch,
) -> httpx.AsyncClient:
    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_EXPOSE_PORT", "true")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", network_name)
    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")

    monkeypatch.setenv("DIRECTOR_V2_CELERY_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_CLIENT_ENABLED", "false")
    monkeypatch.setenv("DIRECTOR_V2_DASK_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("POSTGRES_HOST", "mocked_host")
    monkeypatch.setenv("POSTGRES_USER", "mocked_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "mocked_password")
    monkeypatch.setenv("POSTGRES_DB", "mocked_db")
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "false")

    settings = AppSettings.create_from_envs()

    app = init_app(settings)

    async with LifespanManager(app):
        async with httpx.AsyncClient(
            app=app, base_url="http://testserver/v2"
        ) as client:
            yield client


@pytest.fixture
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

        project_id = f"{dy_static_file_server_project.uuid}"
        await ensure_network_cleanup(docker_client, project_id)


# UTILS


async def _handle_307_if_required(
    director_v2_client: httpx.AsyncClient, director_v0_url: URL, result: httpx.Response
) -> Union[httpx.Response, requests.Response]:
    def _debug_print(
        result: Union[httpx.Response, requests.Response], heading_text: str
    ) -> None:
        print(
            (
                f"{heading_text}\n>>>\n{result.request.method}\n"
                f"{result.request.url}\n{result.request.headers}\n"
                f"<<<\n{result.status_code}\n{result.headers}\n{result.text}\n"
            )
        )

    if result.next_request is not None:
        _debug_print(result, "REDIRECTING[1/2] DV2")

        # replace url endpoint for director-v0 in redirect
        result.next_request.url = httpx.URL(
            str(result.next_request.url).replace(
                "http://director:8080", str(director_v0_url)
            )
        )

        # when both director-v0 and director-v2 were running in containers
        # it was possible to use httpx for GET requests as well
        # since director-v2 is now started on the host directly,
        # a 405 Method Not Allowed is returned
        # using requests is workaround for the issue
        if result.request.method == "GET":
            redirect_result = requests.get(str(result.next_request.url))
        else:
            redirect_result = await director_v2_client.send(result.next_request)

        _debug_print(redirect_result, "REDIRECTING[2/2] DV0")

        return redirect_result

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


def _run_command(command: str) -> str:
    # using asyncio.create_subprocess_shell is slower
    # and sometimes ir randomly hangs forever

    print(f"Running: '{command}'")
    command_result = os.popen(command).read()
    print(command_result)
    return command_result


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
        result = _run_command(
            f"docker service update {service_name} --endpoint-mode=vip"
        )
        assert "verify: Service converged" in result
    else:
        # For a non legacy service, the service_name points to the dynamic-sidecar,
        # but traffic is handeled by the proxy,
        target_service = service_name.replace(
            DYNAMIC_SIDECAR_SERVICE_PREFIX, DYNAMIC_PROXY_SERVICE_PREFIX
        )

    # Finally forward the port on a random assigned port.
    result = _run_command(
        f"docker service update {target_service} --publish-add :{internal_port}"
    )
    assert "verify: Service converged" in result

    # inspect service and fetch the port
    async with aiodocker.Docker() as docker_client:
        service_details = await docker_client.services.inspect(target_service)
        ports = service_details["Endpoint"]["Ports"]

        assert len(ports) == 1, service_details
        exposed_port = ports[0]["PublishedPort"]
        return exposed_port


async def _assert_service_is_available(exposed_port: PositiveInt) -> None:
    service_address = f"http://172.17.0.1:{exposed_port}"
    print(f"checking service @ {service_address}")

    async for attempt in tenacity.AsyncRetrying(
        wait=tenacity.wait_exponential(), stop=tenacity.stop_after_delay(15)
    ):
        with attempt:
            async with httpx.AsyncClient() as client:
                response = await client.get(service_address)
                assert response.status_code == 200


def _get_director_v0_patched_url(url: URL) -> URL:
    return URL(str(url).replace("127.0.0.1", "172.17.0.1"))


# TESTS


async def test_legacy_and_dynamic_sidecar_run(
    dy_static_file_server_project: ProjectAtDB,
    user_db: Dict,
    services_endpoint: Dict[str, URL],
    director_v2_client: httpx.AsyncClient,
    ensure_services_stopped: None,
):
    """
    The test will start 3 dynamic services in the same project and check
    that the legacy and the 2 new dynamic-sidecar boot properly.

    Creates a project containing the following services:
    - dy-static-file-server
    - dy-static-file-server-dynamic-sidecar
    - dy-static-file-server-dynamic-sidecar-compose
    """
    director_v0_url = _get_director_v0_patched_url(services_endpoint["director"])

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
                basepath=f"/x/{service_uuid}" if _is_legacy(node) else None,
            )
        )
    await asyncio.gather(*services_to_start)

    for service_uuid, node in dy_static_file_server_project.workbench.items():
        if _is_legacy(node):
            continue

        await patch_dynamic_service_url(
            # pylint: disable=protected-access
            app=director_v2_client._transport.app,
            node_uuid=service_uuid,
        )

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
