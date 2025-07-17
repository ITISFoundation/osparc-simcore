# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import asyncio
import json
import logging
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import MagicMock

import aiodocker
import pytest
from async_asgi_testclient import TestClient
from async_asgi_testclient.response import Response
from faker import Faker
from fastapi import FastAPI
from models_library.projects import ProjectAtDB, ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKeyVersion
from models_library.services_resources import (
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.common_headers import (
    X_DYNAMIC_SIDECAR_REQUEST_DNS,
    X_DYNAMIC_SIDECAR_REQUEST_SCHEME,
    X_SIMCORE_USER_AGENT,
)
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_service_director_v2.core.application import create_app
from simcore_service_director_v2.core.settings import AppSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from utils import ensure_network_cleanup, patch_dynamic_service_url
from yarl import URL

SERVICE_IS_READY_TIMEOUT = 2 * 60

DIRECTOR_V2_MODULES = "simcore_service_director_v2.modules"

logger = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "agent",
    "catalog",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "redis",
    "storage",
]
pytest_simcore_ops_services_selection = [
    "adminer",
    "minio",
]


@pytest.fixture
def minimal_configuration(
    redis_settings: RedisSettings,
    postgres_db,
    postgres_host_config: dict[str, str],
    dy_static_file_server_dynamic_sidecar_service: dict,
    simcore_services_ready: None,
    rabbit_service: RabbitSettings,
    storage_service: URL,
): ...


@pytest.fixture
def mock_env(mock_env: EnvVarsDict, minimal_configuration) -> None: ...


@pytest.fixture
def user_db(create_registered_user: Callable[..., dict[str, Any]]) -> dict[str, Any]:
    user = create_registered_user()
    return user


@pytest.fixture
def user_id(user_db: dict[str, Any]) -> UserID:
    return UserID(user_db["id"])


@pytest.fixture
async def project_id(
    user_db: dict[str, Any],
    create_project: Callable[..., Awaitable[ProjectAtDB]],
    with_product: dict[str, Any],
) -> str:
    prj = await create_project(user=user_db)
    return f"{prj.uuid}"


@pytest.fixture
def node_uuid(faker: Faker) -> str:
    return f"{faker.uuid4()}"


@pytest.fixture
def start_request_data(
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    dy_static_file_server_dynamic_sidecar_service: dict,
    service_resources: ServiceResourcesDict,
    ensure_swarm_and_networks: None,
    osparc_product_name: str,
    osparc_product_api_base_url: str,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "project_id": project_id,
        "product_name": osparc_product_name,
        "product_api_base_url": osparc_product_api_base_url,
        "service_uuid": node_uuid,
        "service_key": dy_static_file_server_dynamic_sidecar_service["image"]["name"],
        "service_version": dy_static_file_server_dynamic_sidecar_service["image"][
            "tag"
        ],
        "request_scheme": "http",
        "request_dns": "localhost:50000",
        "can_save": True,
        "settings": [
            {
                "name": "resources",
                "type": "Resources",
                "value": {"mem_limit": 17179869184, "cpu_limit": 1000000000},
            },
            {"name": "ports", "type": "int", "value": 80},
            {
                "name": "constraints",
                "type": "string",
                "value": ["node.platform.os == linux"],
            },
        ],
        "paths_mapping": {
            "outputs_path": "/tmp/outputs",  # noqa: S108
            "inputs_path": "/tmp/inputs",  # noqa: S108
        },
        "service_resources": ServiceResourcesDictHelpers.create_jsonable(
            service_resources
        ),
    }


@pytest.fixture
async def director_v2_client(
    mock_env: EnvVarsDict,
    network_name: str,
    redis_settings: RedisSettings,
    monkeypatch: pytest.MonkeyPatch,
    faker: Faker,
) -> AsyncIterable[TestClient]:
    setenvs_from_dict(
        monkeypatch,
        {
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_EXPOSE_PORT": "true",
            "SIMCORE_SERVICES_NETWORK_NAME": network_name,
            "DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED": "true",
            "DYNAMIC_SIDECAR_LOG_LEVEL": "DEBUG",
            "DIRECTOR_V2_LOGLEVEL": "DEBUG",
            "DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS": "{}",
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "false",
            "COMPUTATIONAL_BACKEND_ENABLED": "false",
            "R_CLONE_PROVIDER": "MINIO",
            "S3_ENDPOINT": faker.url(),
            "S3_ACCESS_KEY": faker.pystr(),
            "S3_REGION": faker.pystr(),
            "S3_SECRET_KEY": faker.pystr(),
            "S3_BUCKET_NAME": faker.pystr(),
            # patch host for dynamic-sidecar, not reachable via localhost
            # the dynamic-sidecar (running inside a container) will use
            # this address to reach the rabbit service
            "RABBIT_HOST": f"{get_localhost_ip()}",
            "REDIS_HOST": redis_settings.REDIS_HOST,
            "REDIS_PORT": f"{redis_settings.REDIS_PORT}",
            "REDIS_PASSWORD": f"{redis_settings.REDIS_PASSWORD.get_secret_value()}",
            "DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED": "1",
        },
    )
    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)

    settings = AppSettings.create_from_envs()

    app = create_app(settings)

    async with TestClient(app) as client:
        yield client


@pytest.fixture
async def ensure_services_stopped(
    start_request_data: dict[str, Any], director_v2_client: TestClient
) -> AsyncIterator[None]:
    yield
    # ensure service cleanup when done testing
    async with aiodocker.Docker() as docker_client:
        service_names = {x["Spec"]["Name"] for x in await docker_client.services.list()}

        project_id = start_request_data["service_uuid"]
        for service_name in service_names:
            # if node_uuid is present in the service name it needs to be removed
            if project_id in service_name:
                delete_result = await docker_client.services.delete(service_name)
                assert delete_result is True

        scheduler_interval = (
            director_v2_client.application.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL
        )
        # sleep enough to ensure the observation cycle properly stopped the service
        await asyncio.sleep(2 * scheduler_interval.total_seconds())

        await ensure_network_cleanup(docker_client, project_id)


@pytest.fixture
def mock_project_repository(mocker: MockerFixture) -> None:
    class ExtendedMagicMock(MagicMock):
        @property
        def name(self) -> str:
            return "test_name"

        @property
        def label(self) -> str:
            return "test_label"

    mocker.patch(
        f"{DIRECTOR_V2_MODULES}.db.repositories.projects.ProjectsRepository.get_project",
        side_effect=lambda *args, **kwargs: ExtendedMagicMock(),
    )


@pytest.fixture
def mock_dynamic_sidecar_api_calls(mocker: MockerFixture) -> None:
    class_path = f"{DIRECTOR_V2_MODULES}.dynamic_sidecar.api_client.SidecarsClient"
    for function_name, return_value in [
        ("pull_service_output_ports", None),
        ("restore_service_state", None),
        ("push_service_output_ports", None),
        ("save_service_state", None),
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

    mocker.patch(
        f"{DIRECTOR_V2_MODULES}.dynamic_sidecar.api_client._public.periodic_task_result",
        side_effect=_mocked_context_manger,
    )


@pytest.fixture
async def key_version_expected(
    dy_static_file_server_dynamic_sidecar_service: dict,
    dy_static_file_server_service: dict,
    docker_registry_image_injector: Callable,
) -> list[tuple[ServiceKeyVersion, bool]]:
    results: list[tuple[ServiceKeyVersion, bool]] = []

    sleeper_service = docker_registry_image_injector(
        "itisfoundation/sleeper", "2.1.1", "user@e.mail"
    )

    for image, expected in [
        (dy_static_file_server_dynamic_sidecar_service, True),
        (dy_static_file_server_service, False),
        (sleeper_service, False),
    ]:
        schema = image["schema"]
        results.append(
            (ServiceKeyVersion(key=schema["key"], version=schema["version"]), expected)
        )

    return results


@pytest.mark.flaky(max_runs=3)
async def test_start_status_stop(
    director_v2_client: TestClient,
    node_uuid: str,
    start_request_data: dict[str, Any],
    ensure_services_stopped: None,
    mock_project_repository: None,
    mock_dynamic_sidecar_api_calls: None,
    mock_projects_networks_repository: None,
    mock_projects_repository: None,
    mocked_service_awaits_manual_interventions: None,
    mock_resource_usage_tracker: None,
    mock_osparc_variables_api_auth_rpc: None,
):
    # NOTE: this test does not like it when the catalog is not fully ready!!!

    # starting the service
    response: Response = await director_v2_client.post(
        "/v2/dynamic_services",
        json=start_request_data,
        headers={
            X_DYNAMIC_SIDECAR_REQUEST_DNS: start_request_data["request_dns"],
            X_DYNAMIC_SIDECAR_REQUEST_SCHEME: start_request_data["request_scheme"],
            X_SIMCORE_USER_AGENT: "",
        },
    )
    assert response.status_code == 201, response.text
    assert isinstance(director_v2_client.application, FastAPI)
    await patch_dynamic_service_url(
        app=director_v2_client.application, node_uuid=node_uuid
    )

    # awaiting for service to be running
    data = {}
    async for attempt in AsyncRetrying(
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
        stop=stop_after_delay(SERVICE_IS_READY_TIMEOUT),
        wait=wait_fixed(5),
    ):
        with attempt:
            print(
                f"--> getting service {node_uuid=} status... attempt {attempt.retry_state.attempt_number}"
            )
            response: Response = await director_v2_client.get(
                f"/v2/dynamic_services/{node_uuid}", json=start_request_data
            )
            print("-- sidecar status result %s", response.text)
            assert response.status_code == 200, response.text
            data = response.json()

            assert data.get("service_state", "") == "running"
            print(
                "<-- sidecar is running %s",
                f"{json.dumps(attempt.retry_state.retry_object.statistics)}",
            )

    assert "service_state" in data
    assert data["service_state"] == "running"

    # finally stopping the service
    response: Response = await director_v2_client.delete(
        f"/v2/dynamic_services/{node_uuid}", json=start_request_data
    )
    assert response.status_code == 204, response.text
    assert response.text == ""
