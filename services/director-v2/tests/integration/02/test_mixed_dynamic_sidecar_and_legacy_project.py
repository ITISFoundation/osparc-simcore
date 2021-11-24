# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
import logging
import os
from typing import AsyncIterable, Callable, Dict
from uuid import uuid4

import aiodocker
import httpx
import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from models_library.projects import ProjectAtDB
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from pytest_simcore.helpers.utils_docker import get_ip
from simcore_sdk.node_ports_common import config as node_ports_config
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from utils import (
    assert_all_services_running,
    assert_services_reply_200,
    assert_start_service,
    assert_stop_service,
    ensure_network_cleanup,
    is_legacy,
    patch_dynamic_service_url,
)
from yarl import URL

logger = logging.getLogger(__name__)


# FIXTURES ----------------------------------------------------------------------------------

pytest_simcore_core_services_selection = [
    "catalog",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "minio",
]


@pytest.fixture
def minimal_configuration(
    dy_static_file_server_service: Dict,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: Dict,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services_ready: None,
    storage_service: URL,
    ensure_swarm_and_networks: None,
):
    node_ports_config.STORAGE_ENDPOINT = (
        f"{storage_service.host}:{storage_service.port}"
    )


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
    network_name: str,
    monkeypatch,
) -> AsyncIterable[httpx.AsyncClient]:
    # Works as below line in docker.compose.yml
    # ${DOCKER_REGISTRY:-itisfoundation}/dynamic-sidecar:${DOCKER_IMAGE_TAG:-latest}

    registry = os.environ.get("DOCKER_REGISTRY", "local")
    image_tag = os.environ.get("DOCKER_IMAGE_TAG", "production")

    image_name = f"{registry}/dynamic-sidecar:{image_tag}"

    logger.warning("Patching to: DYNAMIC_SIDECAR_IMAGE=%s", image_name)
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", image_name)
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")

    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_EXPOSE_PORT", "true")
    monkeypatch.setenv("PROXY_EXPOSE_PORT", "true")
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
    # patch host for dynamic-sidecar, not reachable via localhost
    # the dynamic-sidecar (running inside a container) will use
    # this address to reach the rabbit service
    monkeypatch.setenv("RABBIT_HOST", f"{get_ip()}")

    settings = AppSettings.create_from_envs()

    app = init_app(settings)

    async with LifespanManager(app):
        async with httpx.AsyncClient(
            app=app, base_url="http://testserver/v2"
        ) as client:
            yield client


@pytest.fixture
async def ensure_services_stopped(
    dy_static_file_server_project: ProjectAtDB, director_v2_client: httpx.AsyncClient
) -> AsyncIterable[None]:
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

        # pylint: disable=protected-access
        scheduler_interval = (
            director_v2_client._transport.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS
        )
        # sleep enough to ensure the observation cycle properly stopped the service
        await asyncio.sleep(2 * scheduler_interval)
        await ensure_network_cleanup(docker_client, project_id)


@pytest.fixture(scope="module")
def simcore_services_ready_and_change_director_env(
    simcore_services_ready: None, monkeypatch_module
):
    # FIXME: PC: this is trial fix for a nasty bug with environs in simcore_services_ready!!!!
    monkeypatch_module.setenv("DIRECTOR_HOST", "director")
    monkeypatch_module.setenv("DIRECTOR_PORT", "8080")


# TESTS ----------------------------------------------------------------------------------------

pytestmark = pytest.mark.skip(
    reason="FIXME: temp disabled due to faulty environ variables"
)


def test_all_stack_services_running(
    simcore_services_ready_and_change_director_env, dy_static_file_server_project
):
    assert True


async def test_legacy_and_dynamic_sidecar_run(
    dy_static_file_server_project: ProjectAtDB,
    user_db: Dict,
    services_endpoint: Dict[str, URL],
    simcore_services_ready_and_change_director_env: None,
    director_v2_client: httpx.AsyncClient,
    ensure_services_stopped: None,
):
    """
    The test will start 3 dynamic services in the same project and check
    that the legacy and the 2 new dynamic-sidecar boot properly.

    Creates a project containing the following services:
    - dy-static-file-server (legacy)
    - dy-static-file-server-dynamic-sidecar  (sidecared w/ std config)
    - dy-static-file-server-dynamic-sidecar-compose (sidecared w/ docker-compose)
    """
    # FIXME: ANE can you instead parametrize this test?
    # why do we need to run all these services at the same time? it would be simpler one by one

    await asyncio.gather(
        *(
            assert_start_service(
                director_v2_client=director_v2_client,
                # context
                user_id=user_db["id"],
                project_id=str(dy_static_file_server_project.uuid),
                # service
                service_key=node.key,
                service_version=node.version,
                service_uuid=node_id,
                # extra config (legacy)
                basepath=f"/x/{node_id}" if is_legacy(node) else None,
            )
            for node_id, node in dy_static_file_server_project.workbench.items()
        )
    )

    for node_id, node in dy_static_file_server_project.workbench.items():
        if is_legacy(node):
            continue

        await patch_dynamic_service_url(
            # pylint: disable=protected-access
            app=director_v2_client._transport.app,
            node_uuid=node_id,
        )

    assert len(dy_static_file_server_project.workbench) == 3

    await assert_all_services_running(
        director_v2_client,
        workbench=dy_static_file_server_project.workbench,
    )

    # query the service directly and check if it responding accordingly
    await assert_services_reply_200(
        director_v2_client=director_v2_client,
        workbench=dy_static_file_server_project.workbench,
    )

    # finally stop the started services
    await asyncio.gather(
        *(
            assert_stop_service(
                director_v2_client=director_v2_client,
                service_uuid=service_uuid,
            )
            for service_uuid in dy_static_file_server_project.workbench
        )
    )
