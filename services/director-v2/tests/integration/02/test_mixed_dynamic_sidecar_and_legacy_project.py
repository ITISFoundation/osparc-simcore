# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterable, AsyncIterator, Awaitable, Callable, Iterable
from unittest import mock

import aiodocker
import httpx
import pytest
import sqlalchemy as sa
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectAtDB
from models_library.services_resources import ServiceResourcesDict
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
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


pytest_simcore_core_services_selection = [
    "catalog",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "storage",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "minio",
]


@pytest.fixture
def minimal_configuration(
    dy_static_file_server_service: dict,
    dy_static_file_server_dynamic_sidecar_service: dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: dict,
    redis_service: RedisSettings,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    rabbit_service: RabbitSettings,
    simcore_services_ready: None,
    storage_service: URL,
    ensure_swarm_and_networks: None,
):
    ...


@pytest.fixture
def uuid_legacy(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def uuid_dynamic_sidecar(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def uuid_dynamic_sidecar_compose(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def user_dict(registered_user: Callable) -> Iterable[dict[str, Any]]:
    yield registered_user()


@pytest.fixture
async def dy_static_file_server_project(
    minimal_configuration: None,
    user_dict: dict[str, Any],
    project: Callable[..., Awaitable[ProjectAtDB]],
    dy_static_file_server_service: dict,
    dy_static_file_server_dynamic_sidecar_service: dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: dict,
    uuid_legacy: str,
    uuid_dynamic_sidecar: str,
    uuid_dynamic_sidecar_compose: str,
) -> ProjectAtDB:
    def _assemble_node_data(spec: dict, label: str) -> dict[str, str]:
        return {
            "key": spec["image"]["name"],
            "version": spec["image"]["tag"],
            "label": label,
        }

    return await project(
        user=user_dict,
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
        },
    )


@pytest.fixture
async def director_v2_client(
    redis_service: RedisSettings,
    minimal_configuration: None,
    minio_config: dict[str, Any],
    storage_service: URL,
    network_name: str,
    monkeypatch: MonkeyPatch,
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
    monkeypatch.setenv("DYNAMIC_SIDECAR_LOG_LEVEL", "DEBUG")

    monkeypatch.setenv("SC_BOOT_MODE", "production")
    monkeypatch.setenv("DYNAMIC_SIDECAR_EXPOSE_PORT", "true")
    monkeypatch.setenv("PROXY_EXPOSE_PORT", "true")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", network_name)
    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "true")

    monkeypatch.setenv("POSTGRES_HOST", f"{get_localhost_ip()}")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "false")
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_ENABLED", "false")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", minio_config["client"]["endpoint"])
    monkeypatch.setenv("S3_ACCESS_KEY", minio_config["client"]["access_key"])
    monkeypatch.setenv("S3_SECRET_KEY", minio_config["client"]["secret_key"])
    monkeypatch.setenv("S3_BUCKET_NAME", minio_config["bucket_name"])
    monkeypatch.setenv("S3_SECURE", f"{minio_config['client']['secure']}")

    # patch host for dynamic-sidecar, not reachable via localhost
    # the dynamic-sidecar (running inside a container) will use
    # this address to reach the rabbit service
    monkeypatch.setenv("RABBIT_HOST", f"{get_localhost_ip()}")

    monkeypatch.setenv("REDIS_HOST", redis_service.REDIS_HOST)
    monkeypatch.setenv("REDIS_PORT", f"{redis_service.REDIS_PORT}")

    settings = AppSettings.create_from_envs()

    app = init_app(settings)

    async with LifespanManager(app), httpx.AsyncClient(
        app=app, base_url="http://testserver"
    ) as client:
        yield client


@pytest.fixture
async def ensure_services_stopped(
    dy_static_file_server_project: ProjectAtDB,
    director_v2_client: httpx.AsyncClient,
    minimal_app: FastAPI,
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
            minimal_app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS
        )
        # sleep enough to ensure the observation cycle properly stopped the service
        await asyncio.sleep(2 * scheduler_interval)
        await ensure_network_cleanup(docker_client, project_id)


@pytest.fixture
def mock_sidecars_client(mocker: MockerFixture) -> mock.Mock:
    class_path = (
        "simcore_service_director_v2.modules.dynamic_sidecar.api_client.SidecarsClient"
    )
    for function_name, return_value in [
        ("pull_service_output_ports", None),
        ("restore_service_state", None),
        ("push_service_output_ports", None),
    ]:
        mocker.patch(
            f"{class_path}.{function_name}",
            # pylint: disable=cell-var-from-loop
            side_effect=lambda *args, **kwargs: return_value,
        )

    # also patch the long_running_tasks client context mangers handling the above
    # requests
    @asynccontextmanager
    async def _mocked_context_manger(*args, **kwargs) -> AsyncIterator[None]:
        yield

    return mocker.patch(
        "simcore_service_director_v2.modules.dynamic_sidecar.api_client._public.periodic_task_result",
        side_effect=_mocked_context_manger,
    )


@pytest.mark.flaky(max_runs=3)
async def test_legacy_and_dynamic_sidecar_run(
    dy_static_file_server_project: ProjectAtDB,
    user_dict: dict[str, Any],
    services_endpoint: dict[str, URL],
    director_v2_client: httpx.AsyncClient,
    osparc_product_name: str,
    ensure_services_stopped: None,
    mock_projects_networks_repository: None,
    mock_sidecars_client: None,
    service_resources: ServiceResourcesDict,
    mocked_service_awaits_manual_interventions: None,
    minimal_app: FastAPI,
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
                product_name=osparc_product_name,
                user_id=user_dict["id"],
                project_id=str(dy_static_file_server_project.uuid),
                # service
                service_key=node.key,
                service_version=node.version,
                service_uuid=node_id,
                # extra config (legacy)
                basepath=f"/x/{node_id}" if is_legacy(node) else None,
                catalog_url=services_endpoint["catalog"],
            )
            for node_id, node in dy_static_file_server_project.workbench.items()
        )
    )

    for node_id, node in dy_static_file_server_project.workbench.items():
        if is_legacy(node):
            continue

        await patch_dynamic_service_url(
            # pylint: disable=protected-access
            app=minimal_app,
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
