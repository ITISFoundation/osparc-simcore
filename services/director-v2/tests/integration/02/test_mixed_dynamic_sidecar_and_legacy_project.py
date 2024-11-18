# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import logging
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, cast
from unittest import mock

import aiodocker
import httpx
import pytest
import sqlalchemy as sa
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectAtDB
from models_library.services_resources import ServiceResourcesDict
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
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
    "agent",
    "catalog",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]

pytest_simcore_ops_services_selection = ["adminer", "minio", "portainer"]


@pytest.fixture()
def mock_env(
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    redis_service: RedisSettings,
    rabbit_service: RabbitSettings,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    minio_s3_settings_envs: EnvVarsDict,
    storage_service: URL,
    network_name: str,
    services_endpoint: dict[str, URL],
) -> EnvVarsDict:
    director_host = services_endpoint["director"].host
    assert director_host
    director_port = services_endpoint["director"].port
    assert director_port

    catalog_host = services_endpoint["catalog"].host
    assert catalog_host
    catalog_port = services_endpoint["catalog"].port
    assert catalog_port

    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)
    mock_env.pop("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", None)

    return mock_env | setenvs_from_dict(
        monkeypatch,
        {
            "DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS": "{}",
            "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
            "SWARM_STACK_NAME": "pytest-simcore",
            "DYNAMIC_SIDECAR_LOG_LEVEL": "DEBUG",
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_EXPOSE_PORT": "true",
            "PROXY_EXPOSE_PORT": "true",
            "SIMCORE_SERVICES_NETWORK_NAME": network_name,
            "DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED": "true",
            "POSTGRES_HOST": f"{get_localhost_ip()}",
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "false",
            "COMPUTATIONAL_BACKEND_ENABLED": "false",
            "R_CLONE_PROVIDER": "MINIO",
            "DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED": "1",
            "DIRECTOR_HOST": director_host,
            "DIRECTOR_PORT": f"{director_port}",
            "CATALOG_HOST": catalog_host,
            "CATALOG_PORT": f"{catalog_port}",
        },
    )


@pytest.fixture
def minimal_configuration(
    dy_static_file_server_service: dict,
    dy_static_file_server_dynamic_sidecar_service: dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: dict,
    simcore_services_ready: None,
    ensure_swarm_and_networks: None,
):
    ...


@pytest.fixture
def uuid_legacy(faker: Faker) -> str:
    return cast(str, faker.uuid4())


@pytest.fixture
def uuid_dynamic_sidecar(faker: Faker) -> str:
    return cast(str, faker.uuid4())


@pytest.fixture
def uuid_dynamic_sidecar_compose(faker: Faker) -> str:
    return cast(str, faker.uuid4())


@pytest.fixture
def user_dict(registered_user: Callable) -> dict[str, Any]:
    return registered_user()


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
async def ensure_services_stopped(
    dy_static_file_server_project: ProjectAtDB,
    initialized_app: FastAPI,
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
            initialized_app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL
        )
        # sleep enough to ensure the observation cycle properly stopped the service
        await asyncio.sleep(2 * scheduler_interval.total_seconds())
        await ensure_network_cleanup(docker_client, project_id)


@pytest.fixture
def mock_sidecars_client(mocker: MockerFixture) -> mock.Mock:
    class_path = (
        "simcore_service_director_v2.modules.dynamic_sidecar.api_client.SidecarsClient"
    )
    for function_name, return_value in [
        ("pull_service_output_ports", 0),
        ("restore_service_state", 0),
        ("push_service_output_ports", None),
        ("save_service_state", 0),
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
    initialized_app: FastAPI,
    wait_for_catalog_service: Callable[[UserID, str], Awaitable[None]],
    dy_static_file_server_project: ProjectAtDB,
    user_dict: dict[str, Any],
    services_endpoint: dict[str, URL],
    async_client: httpx.AsyncClient,
    osparc_product_name: str,
    ensure_services_stopped: None,
    mock_projects_networks_repository: None,
    mock_sidecars_client: mock.Mock,
    service_resources: ServiceResourcesDict,
    mocked_service_awaits_manual_interventions: None,
    mock_resource_usage_tracker: None,
    mock_osparc_variables_api_auth_rpc: None,
):
    """
    The test will start 3 dynamic services in the same project and check
    that the legacy and the 2 new dynamic-sidecar boot properly.

    Creates a project containing the following services:
    - dy-static-file-server (legacy)
    - dy-static-file-server-dynamic-sidecar  (sidecared w/ std config)
    - dy-static-file-server-dynamic-sidecar-compose (sidecared w/ docker-compose)
    """
    await wait_for_catalog_service(user_dict["id"], osparc_product_name)
    await asyncio.gather(
        *(
            assert_start_service(
                director_v2_client=async_client,
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

        await patch_dynamic_service_url(app=initialized_app, node_uuid=node_id)

    assert len(dy_static_file_server_project.workbench) == 3

    await assert_all_services_running(
        async_client,
        workbench=dy_static_file_server_project.workbench,
    )

    # query the service directly and check if it responding accordingly
    await assert_services_reply_200(
        director_v2_client=async_client,
        workbench=dy_static_file_server_project.workbench,
    )

    # finally stop the started services
    await asyncio.gather(
        *(
            assert_stop_service(
                director_v2_client=async_client,
                service_uuid=service_uuid,
            )
            for service_uuid in dy_static_file_server_project.workbench
        )
    )
