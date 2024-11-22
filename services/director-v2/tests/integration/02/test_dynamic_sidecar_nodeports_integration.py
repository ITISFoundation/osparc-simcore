# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint:disable=too-many-positional-arguments

import asyncio
import hashlib
import json
import logging
import os
from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Coroutine
from pathlib import Path
from typing import Any, NamedTuple, cast
from uuid import uuid4

import aioboto3
import aiodocker
import aiopg.sa
import httpx
import pytest
import sqlalchemy as sa
from aiodocker.containers import DockerContainer
from aiopg.sa import Engine
from faker import Faker
from fastapi import FastAPI
from helpers.shared_comp_utils import (
    assert_and_wait_for_pipeline_status,
    assert_computation_task_out_obj,
)
from models_library.api_schemas_directorv2.comp_tasks import ComputationGet
from models_library.clusters import DEFAULT_CLUSTER_ID, InternalClusterAuthentication
from models_library.projects import (
    Node,
    NodesDict,
    ProjectAtDB,
    ProjectID,
    ProjectIDStr,
)
from models_library.projects_networks import (
    PROJECT_NETWORK_PREFIX,
    ContainerAliases,
    NetworksWithAliases,
    ProjectsNetworks,
)
from models_library.projects_nodes_io import NodeID, NodeIDStr
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.users import UserID
from pydantic import AnyHttpUrl, TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.fastapi.long_running_tasks.client import (
    Client,
    ProgressMessage,
    ProgressPercent,
    TaskId,
    periodic_task_result,
)
from servicelib.progress_bar import ProgressBarData
from servicelib.sequences_utils import pairwise
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.storage import StorageSettings
from settings_library.tracing import TracingSettings
from simcore_postgres_database.models.comp_pipeline import comp_pipeline
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.projects_networks import projects_networks
from simcore_postgres_database.models.services import services_access_rights
from simcore_sdk import node_ports_v2
from simcore_sdk.node_data import data_manager
from simcore_sdk.node_ports_common.file_io_utils import LogRedirectCB
from simcore_sdk.node_ports_v2 import DBManager, Nodeports, Port
from simcore_service_director_v2.constants import DYNAMIC_SIDECAR_SERVICE_PREFIX
from simcore_service_director_v2.core.dynamic_services_settings.sidecar import (
    RCloneSettings,
)
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.modules import storage as dv2_modules_storage
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_attempt, stop_after_delay
from tenacity.wait import wait_fixed
from utils import (
    assert_all_services_running,
    assert_retrieve_service,
    assert_services_reply_200,
    assert_start_service,
    assert_stop_service,
    ensure_network_cleanup,
    ensure_volume_cleanup,
    is_legacy,
    patch_dynamic_service_url,
    run_command,
    sleep_for,
)
from yarl import URL

pytest_simcore_core_services_selection = [
    "agent",
    "catalog",
    "dask-scheduler",
    "dask-sidecar",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "adminer",
    "minio",
    "portainer",
]


class ServicesNodeUUIDs(NamedTuple):
    sleeper: str
    dy: str
    dy_compose_spec: str


class InputsOutputs(NamedTuple):
    inputs: dict[str, Any]
    outputs: dict[str, Any]


DY_VOLUMES: str = "/dy-volumes/"
DY_SERVICES_STATE_PATH: Path = Path(DY_VOLUMES) / "workdir/generated-data"
DY_SERVICES_R_CLONE_DIR_NAME: str = (
    # pylint: disable=bad-str-strip-call
    str(DY_SERVICES_STATE_PATH)
    .strip(DY_VOLUMES)
    .replace("/", "_")
)
TIMEOUT_DETECT_DYNAMIC_SERVICES_STOPPED = 60
TIMEOUT_OUTPUTS_UPLOAD_FINISH_DETECTED = 60
POSSIBLE_ISSUE_WORKAROUND = 10
WAIT_FOR_R_CLONE_VOLUME_TO_SYNC_DATA = 30


logger = logging.getLogger(__name__)


@pytest.fixture
async def minimal_configuration(
    wait_for_catalog_service: Callable[[UserID, str], Awaitable[None]],
    sleeper_service: dict,
    dy_static_file_server_dynamic_sidecar_service: dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: dict,
    redis_service: RedisSettings,
    postgres_db: sa.engine.Engine,
    postgres_host_config: dict[str, str],
    rabbit_service: RabbitSettings,
    simcore_services_ready: None,
    storage_service: URL,
    dask_scheduler_service: str,
    dask_sidecar_service: None,
    ensure_swarm_and_networks: None,
    minio_s3_settings_envs: EnvVarsDict,
    current_user: dict[str, Any],
    osparc_product_name: str,
) -> AsyncIterator[None]:
    await wait_for_catalog_service(current_user["id"], osparc_product_name)
    with postgres_db.connect() as conn:
        # pylint: disable=no-value-for-parameter
        conn.execute(comp_tasks.delete())
        conn.execute(comp_pipeline.delete())
        # NOTE: ensure access to services to everyone [catalog access needed]
        for service in (
            dy_static_file_server_dynamic_sidecar_service,
            dy_static_file_server_dynamic_sidecar_compose_spec_service,
        ):
            service_image = service["image"]
            conn.execute(
                services_access_rights.insert().values(
                    key=service_image["name"],
                    version=service_image["tag"],
                    gid=1,
                    execute_access=1,
                    write_access=0,
                    product_name=osparc_product_name,
                )
            )
        yield


@pytest.fixture
def fake_dy_workbench(
    mocks_dir: Path,
    sleeper_service: dict,
    dy_static_file_server_dynamic_sidecar_service: dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: dict,
) -> dict[str, Any]:
    dy_workbench_template = mocks_dir / "fake_dy_workbench_template.json"
    assert dy_workbench_template.exists()

    file_content = dy_workbench_template.read_text()
    file_as_dict = json.loads(file_content)

    def _assert_version(registry_service_data: dict) -> None:
        key = registry_service_data["schema"]["key"]
        version = registry_service_data["schema"]["version"]
        found = False
        for workbench_service_data in file_as_dict.values():
            if (
                workbench_service_data["key"] == key
                and workbench_service_data["version"] == version
            ):
                found = True
                break

        # when updating the services, this check will fail
        # bump versions in the mocks if no breaking changes
        # have been made
        error_message = (
            f"Did not find service: key={key}, version={version}! in {file_as_dict}"
        )
        assert found is True, error_message

    _assert_version(sleeper_service)
    _assert_version(dy_static_file_server_dynamic_sidecar_service)
    _assert_version(dy_static_file_server_dynamic_sidecar_compose_spec_service)

    return file_as_dict


@pytest.fixture
def fake_dy_success(mocks_dir: Path) -> dict[str, Any]:
    fake_dy_status_success = mocks_dir / "fake_dy_status_success.json"
    assert fake_dy_status_success.exists()
    return json.loads(fake_dy_status_success.read_text())


@pytest.fixture
def services_node_uuids(
    fake_dy_workbench: dict[str, Any],
    sleeper_service: dict,
    dy_static_file_server_dynamic_sidecar_service: dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: dict,
) -> ServicesNodeUUIDs:
    def _get_node_uuid(registry_service_data: dict) -> str:
        key = registry_service_data["schema"]["key"]
        version = registry_service_data["schema"]["version"]

        found_node_uuid: str | None = None
        for node_uuid, workbench_service_data in fake_dy_workbench.items():
            if (
                workbench_service_data["key"] == key
                and workbench_service_data["version"] == version
            ):
                found_node_uuid = node_uuid
                break
        assert found_node_uuid is not None, f"No node_uuid found for {key}:{version}"
        return found_node_uuid

    return ServicesNodeUUIDs(
        sleeper=_get_node_uuid(sleeper_service),
        dy=_get_node_uuid(dy_static_file_server_dynamic_sidecar_service),
        dy_compose_spec=_get_node_uuid(
            dy_static_file_server_dynamic_sidecar_compose_spec_service
        ),
    )


@pytest.fixture
def current_user(registered_user: Callable) -> dict[str, Any]:
    return registered_user()


@pytest.fixture
async def current_study(
    current_user: dict[str, Any],
    project: Callable[..., Awaitable[ProjectAtDB]],
    fake_dy_workbench: dict[str, Any],
    async_client: httpx.AsyncClient,
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
) -> ProjectAtDB:
    project_at_db = await project(current_user, workbench=fake_dy_workbench)

    # create entries in comp_task table in order to pull output ports
    await create_pipeline(
        async_client,
        project=project_at_db,
        user_id=current_user["id"],
        start_pipeline=False,
        product_name=osparc_product_name,
    )

    return project_at_db


@pytest.fixture
def workbench_dynamic_services(
    current_study: ProjectAtDB, sleeper_service: dict
) -> dict[NodeIDStr, Node]:
    sleeper_key = sleeper_service["schema"]["key"]
    result = {k: v for k, v in current_study.workbench.items() if v.key != sleeper_key}
    assert len(result) == 2
    return result


@pytest.fixture
async def db_manager(aiopg_engine: aiopg.sa.engine.Engine) -> DBManager:
    return DBManager(aiopg_engine)


def _is_docker_r_clone_plugin_installed() -> bool:
    return "rclone:" in run_command("docker plugin ls")


@pytest.fixture(
    scope="session",
    params={
        # NOTE: There is an issue with the docker rclone volume plugin:
        # SEE https://github.com/rclone/rclone/issues/6059
        # Disabling rclone test until this is fixed.
        # "true",
        "false",
    },
)
def dev_feature_r_clone_enabled(request) -> str:
    if request.param == "true" and not _is_docker_r_clone_plugin_installed():
        pytest.skip("Required docker plugin `rclone` not installed.")
    return request.param


@pytest.fixture
async def patch_storage_setup(
    mocker: MockerFixture,
) -> None:
    local_settings = StorageSettings.create_from_envs()

    original_setup = dv2_modules_storage.setup

    def setup(
        app: FastAPI,
        storage_settings: StorageSettings,
        tracing_settings: TracingSettings | None,
    ) -> None:
        original_setup(
            app, storage_settings=local_settings, tracing_settings=tracing_settings
        )

    mocker.patch("simcore_service_director_v2.modules.storage.setup", side_effect=setup)


@pytest.fixture
def mock_env(
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    network_name: str,
    dev_feature_r_clone_enabled: str,
    dask_scheduler_service: str,
    dask_scheduler_auth: InternalClusterAuthentication,
    minimal_configuration: None,
    patch_storage_setup: None,
) -> None:
    # Works as below line in docker.compose.yml
    # ${DOCKER_REGISTRY:-itisfoundation}/dynamic-sidecar:${DOCKER_IMAGE_TAG:-latest}

    registry = os.environ.get("DOCKER_REGISTRY", "local")
    image_tag = os.environ.get("DOCKER_IMAGE_TAG", "production")

    image_name = f"{registry}/dynamic-sidecar:{image_tag}"

    local_settings = StorageSettings.create_from_envs()

    logger.warning("Patching to: DYNAMIC_SIDECAR_IMAGE=%s", image_name)
    setenvs_from_dict(
        monkeypatch,
        {
            "STORAGE_HOST": "storage",
            "STORAGE_PORT": "8080",
            "NODE_PORTS_STORAGE_AUTH": json.dumps(
                {
                    "STORAGE_HOST": local_settings.STORAGE_HOST,
                    "STORAGE_PORT": local_settings.STORAGE_PORT,
                }
            ),
            "STORAGE_ENDPOINT": "storage:8080",
            "DYNAMIC_SIDECAR_IMAGE": image_name,
            "DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS": "{}",
            "TRAEFIK_SIMCORE_ZONE": "test_traefik_zone",
            "SWARM_STACK_NAME": "pytest-simcore",
            "SC_BOOT_MODE": "production",
            "DYNAMIC_SIDECAR_EXPOSE_PORT": "true",
            "DYNAMIC_SIDECAR_LOG_LEVEL": "DEBUG",
            "PROXY_EXPOSE_PORT": "true",
            "SIMCORE_SERVICES_NETWORK_NAME": network_name,
            "DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED": "true",
            "DIRECTOR_V2_LOGLEVEL": "DEBUG",
            "DYNAMIC_SIDECAR_TRAEFIK_ACCESS_LOG": "true",
            "DYNAMIC_SIDECAR_TRAEFIK_LOGLEVEL": "debug",
            # patch host for dynamic-sidecar, not reachable via localhost
            # the dynamic-sidecar (running inside a container) will use
            # this address to reach the rabbit service
            "RABBIT_HOST": f"{get_localhost_ip()}",
            "POSTGRES_HOST": f"{get_localhost_ip()}",
            "R_CLONE_PROVIDER": "MINIO",
            "DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED": dev_feature_r_clone_enabled,
            "COMPUTATIONAL_BACKEND_ENABLED": "true",
            "COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED": "true",
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL": dask_scheduler_service,
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH": dask_scheduler_auth.model_dump_json(),
            "DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED": "1",
        },
    )
    monkeypatch.delenv("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", raising=False)


@pytest.fixture
async def cleanup_services_and_networks(
    workbench_dynamic_services: dict[str, Node],
    current_study: ProjectAtDB,
    initialized_app: FastAPI,
) -> AsyncIterable[None]:
    yield None
    # ensure service cleanup when done testing
    async with aiodocker.Docker() as docker_client:
        service_names = {x["Spec"]["Name"] for x in await docker_client.services.list()}

        # grep the names of the services
        for node_uuid in workbench_dynamic_services:
            for service_name in service_names:
                # if node_uuid is present in the service name it needs to be removed
                if node_uuid in service_name:
                    delete_result = await docker_client.services.delete(service_name)
                    assert delete_result is True

        project_id = f"{current_study.uuid}"

        # sleep enough to ensure the observation cycle properly stopped the service
        await ensure_network_cleanup(docker_client, project_id)

        # remove pending volumes for service
        for node_uuid in workbench_dynamic_services:
            await ensure_volume_cleanup(docker_client, node_uuid)


@pytest.fixture
async def projects_networks_db(
    initialized_app: FastAPI, current_study: ProjectAtDB
) -> None:
    # NOTE: director-v2 does not have access to the webserver which creates this
    # injecting all dynamic-sidecar started services on a default networks

    container_aliases: ContainerAliases = ContainerAliases.model_validate({})

    for k, (node_uuid, node) in enumerate(current_study.workbench.items()):
        if not is_legacy(node):
            container_aliases[node_uuid] = f"networkable_alias_{k}"

    networks_with_aliases: NetworksWithAliases = NetworksWithAliases.model_validate({})
    default_network_name = f"{PROJECT_NETWORK_PREFIX}_{current_study.uuid}_test"
    networks_with_aliases[default_network_name] = container_aliases

    projects_networks_to_insert = ProjectsNetworks(
        project_uuid=current_study.uuid, networks_with_aliases=networks_with_aliases
    )

    engine: Engine = initialized_app.state.engine

    async with engine.acquire() as conn:
        row_data = projects_networks_to_insert.model_dump()
        insert_stmt = pg_insert(projects_networks).values(**row_data)
        upsert_snapshot = insert_stmt.on_conflict_do_update(
            constraint=projects_networks.primary_key, set_=row_data
        )
        await conn.execute(upsert_snapshot)


@pytest.fixture
def mock_io_log_redirect_cb() -> LogRedirectCB:
    async def _mocked_function(*args, **kwargs) -> None:
        pass

    return _mocked_function


async def _get_mapped_nodeports_values(
    user_id: UserID, project_id: str, workbench: NodesDict, db_manager: DBManager
) -> dict[str, InputsOutputs]:
    result: dict[str, InputsOutputs] = {}

    for node_uuid in workbench:
        PORTS: Nodeports = await node_ports_v2.ports(
            user_id=user_id,
            project_id=ProjectIDStr(project_id),
            node_uuid=TypeAdapter(NodeIDStr).validate_python(node_uuid),
            db_manager=db_manager,
        )
        result[str(node_uuid)] = InputsOutputs(
            inputs={
                node_input.key: node_input
                for node_input in (await PORTS.inputs).values()
            },
            outputs={
                node_output.key: node_output
                for node_output in (await PORTS.outputs).values()
            },
        )

    return result


def _print_values_to_assert(**kwargs) -> None:
    print("Values to assert", ", ".join(f"{k}={v}" for k, v in kwargs.items()))


async def _assert_port_values(
    user_id: UserID,
    current_study: ProjectAtDB,
    db_manager: DBManager,
    services_node_uuids: ServicesNodeUUIDs,
    *,
    only_files: bool,
    include_dy_compose_spec: bool,
):
    mapped = await _get_mapped_nodeports_values(
        user_id, f"{current_study.uuid}", current_study.workbench, db_manager
    )

    print("Nodeport mapped values")
    for node_uuid, inputs_outputs in mapped.items():
        print("Port values for", node_uuid)
        print("INPUTS")
        for value in inputs_outputs.inputs.values():
            print(value.key, value)
        print("OUTPUTS")
        for value in inputs_outputs.outputs.values():
            print(value.key, value)

    # files

    async def _int_value_port(port: Port) -> int | None:
        file_path = cast(Path | None, await port.get())
        if file_path is None:
            return None
        return int(file_path.read_text())

    sleeper_out_1 = await _int_value_port(
        mapped[services_node_uuids.sleeper].outputs["out_1"]
    )

    dy_file_input = await _int_value_port(
        mapped[services_node_uuids.dy].inputs["file_input"]
    )
    dy_file_output = await _int_value_port(
        mapped[services_node_uuids.dy].outputs["file_output"]
    )

    dy_compose_spec_file_input = await _int_value_port(
        mapped[services_node_uuids.dy_compose_spec].inputs["file_input"]
    )
    dy_compose_spec_file_output = await _int_value_port(
        mapped[services_node_uuids.dy_compose_spec].outputs["file_output"]
    )

    _print_values_to_assert(
        sleeper_out_1=sleeper_out_1,
        dy_file_input=dy_file_input,
        dy_file_output=dy_file_output,
        dy_compose_spec_file_input=dy_compose_spec_file_input,
        dy_compose_spec_file_output=dy_compose_spec_file_output,
    )

    assert sleeper_out_1 == dy_file_input
    assert sleeper_out_1 == dy_file_output
    if include_dy_compose_spec:
        assert sleeper_out_1 == dy_compose_spec_file_input
        assert sleeper_out_1 == dy_compose_spec_file_output

    if only_files:
        return

    # integer values
    sleeper_out_2 = await mapped[services_node_uuids.sleeper].outputs["out_2"].get()
    dy_integer_input = (
        await mapped[services_node_uuids.dy].inputs["integer_input"].get()
    )
    dy_integer_output = (
        await mapped[services_node_uuids.dy].outputs["integer_output"].get()
    )

    dy_compose_spec_integer_input = (
        await mapped[services_node_uuids.dy_compose_spec].inputs["integer_input"].get()
    )
    dy_compose_spec_integer_output = (
        await mapped[services_node_uuids.dy_compose_spec]
        .outputs["integer_output"]
        .get()
    )

    _print_values_to_assert(
        sleeper_out_2=sleeper_out_2,
        dy_integer_input=dy_integer_input,
        dy_integer_output=dy_integer_output,
        dy_compose_spec_integer_input=dy_compose_spec_integer_input,
        dy_compose_spec_integer_output=dy_compose_spec_integer_output,
    )

    assert sleeper_out_2 == dy_integer_input
    assert sleeper_out_2 == dy_integer_output
    if include_dy_compose_spec:
        assert sleeper_out_2 == dy_compose_spec_integer_input
        assert sleeper_out_2 == dy_compose_spec_integer_output


async def _container_id_via_services(service_uuid: str) -> str:
    container_id = None

    service_name = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{service_uuid}"
    async with aiodocker.Docker() as docker_client:
        service_id = None
        for service in await docker_client.services.list():
            if service["Spec"]["Name"] == service_name:
                service_id = service["ID"]
                break
        assert (
            service_id is not None
        ), f"No service found for service name: {service_name}"

        for task in await docker_client.tasks.list():
            if task["ServiceID"] == service_id:
                assert task["Status"]["State"] == "running"
                container_id = task["Status"]["ContainerStatus"]["ContainerID"]
                break

    assert (
        container_id is not None
    ), f"No container found for service name {service_name}"

    return container_id


async def _fetch_data_from_container(
    dir_tag: str, service_uuid: str, temp_dir: Path
) -> Path:
    container_id = await _container_id_via_services(service_uuid)

    target_path = temp_dir / f"container_{dir_tag}_{uuid4()}"
    target_path.mkdir(parents=True, exist_ok=True)

    run_command(f"docker cp {container_id}:{DY_SERVICES_STATE_PATH}/. {target_path}")

    return target_path


async def _fetch_data_via_data_manager(
    r_clone_settings: RCloneSettings,
    dir_tag: str,
    user_id: UserID,
    project_id: ProjectID,
    service_uuid: NodeID,
    temp_dir: Path,
    io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
) -> Path:
    save_to = temp_dir / f"data-manager_{dir_tag}_{uuid4()}"
    save_to.mkdir(parents=True, exist_ok=True)

    assert (
        await data_manager._state_metadata_entry_exists(  # noqa: SLF001
            user_id=user_id,
            project_id=project_id,
            node_uuid=service_uuid,
            path=DY_SERVICES_STATE_PATH,
            is_archive=False,
        )
        is True
    )

    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        await data_manager._pull_directory(  # noqa: SLF001
            user_id=user_id,
            project_id=project_id,
            node_uuid=service_uuid,
            destination_path=DY_SERVICES_STATE_PATH,
            save_to=save_to,
            io_log_redirect_cb=io_log_redirect_cb,
            r_clone_settings=r_clone_settings,
            progress_bar=progress_bar,
            aws_s3_cli_settings=None,
        )

    return save_to


async def _fetch_data_via_aioboto(
    r_clone_settings: RCloneSettings,
    dir_tag: str,
    temp_dir: Path,
    node_id: NodeIDStr,
    project_id: ProjectID,
) -> Path:
    save_to = temp_dir / f"aioboto_{dir_tag}_{uuid4()}"
    save_to.mkdir(parents=True, exist_ok=True)

    session = aioboto3.Session(
        aws_access_key_id=r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        aws_secret_access_key=r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
    )
    async with session.resource(
        "s3", endpoint_url=r_clone_settings.R_CLONE_S3.S3_ENDPOINT
    ) as s3:
        bucket = await s3.Bucket(r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME)
        async for s3_object in bucket.objects.all():
            key_path = f"{project_id}/{node_id}/{DY_SERVICES_R_CLONE_DIR_NAME}/"
            if s3_object.key.startswith(key_path):
                file_object = await s3_object.get()
                file_path = save_to / s3_object.key.replace(key_path, "")
                print(f"Saving file to {file_path}")
                file_content = await file_object["Body"].read()
                file_path.write_bytes(file_content)

    return save_to


async def _start_and_wait_for_dynamic_services_ready(
    director_v2_client: httpx.AsyncClient,
    product_name: str,
    user_id: UserID,
    workbench_dynamic_services: dict[str, Node],
    current_study: ProjectAtDB,
    catalog_url: URL,
) -> dict[str, str]:
    # start dynamic services
    await asyncio.gather(
        *(
            assert_start_service(
                director_v2_client=director_v2_client,
                product_name=product_name,
                user_id=user_id,
                project_id=str(current_study.uuid),
                service_key=node.key,
                service_version=node.version,
                service_uuid=service_uuid,
                basepath=f"/x/{service_uuid}" if is_legacy(node) else None,
                catalog_url=catalog_url,
            )
            for service_uuid, node in workbench_dynamic_services.items()
        )
    )

    dynamic_services_urls: dict[str, str] = {}

    for service_uuid in workbench_dynamic_services:
        dynamic_service_url = await patch_dynamic_service_url(
            # pylint: disable=protected-access
            app=director_v2_client._transport.app,  # type: ignore # noqa: SLF001
            node_uuid=service_uuid,
        )
        dynamic_services_urls[service_uuid] = dynamic_service_url

    await assert_all_services_running(
        director_v2_client, workbench=workbench_dynamic_services
    )

    await assert_services_reply_200(
        director_v2_client=director_v2_client,
        workbench=workbench_dynamic_services,
    )

    return dynamic_services_urls


async def _wait_for_dy_services_to_fully_stop(
    director_v2_client: httpx.AsyncClient,
) -> None:
    # pylint: disable=protected-access
    app: FastAPI = director_v2_client._transport.app  # type: ignore # noqa: SLF001
    to_observe = (
        app.state.dynamic_sidecar_scheduler.scheduler._to_observe  # noqa: SLF001
    )

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(TIMEOUT_DETECT_DYNAMIC_SERVICES_STOPPED),
        wait=wait_fixed(1),
        reraise=True,
        retry=retry_if_exception_type(TryAgain),
    ):
        with attempt:
            print(
                f"Sleeping for {attempt.retry_state.attempt_number}/{TIMEOUT_DETECT_DYNAMIC_SERVICES_STOPPED} "
                "seconds while waiting for removal of all dynamic-sidecars"
            )
            if len(to_observe) != 0:
                raise TryAgain


def _assert_same_set(*sets_to_compare: set[Any]) -> None:
    for first, second in pairwise(sets_to_compare):
        assert first == second


def _get_file_hashes_in_path(path_to_hash: Path) -> set[tuple[Path, str]]:
    def _hash_path(path: Path):
        sha256_hash = hashlib.sha256()
        with Path.open(path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _relative_path(root_path: Path, full_path: Path) -> Path:
        return full_path.relative_to(root_path)

    if path_to_hash.is_file():
        return {(_relative_path(path_to_hash, path_to_hash), _hash_path(path_to_hash))}

    return {
        (_relative_path(path_to_hash, path), _hash_path(path))
        for path in path_to_hash.rglob("*")
    }


_CONTROL_TESTMARK_DY_SIDECAR_NODEPORT_UPLOADED_MESSAGE = (
    "TEST: test_nodeports_integration DO NOT REMOVE"
)


async def _assert_push_non_file_outputs(
    initialized_app: FastAPI, director_v2_client: httpx.AsyncClient, service_uuid: str
) -> None:
    result = await director_v2_client.post(
        f"/v2/dynamic_scheduler/services/{service_uuid}/outputs:push"
    )
    assert result.status_code == httpx.codes.ACCEPTED
    task_id: TaskId = result.json()

    logger.debug("Going to poll task %s", task_id)

    async def _debug_progress_callback(
        message: ProgressMessage, percent: ProgressPercent | None, task_id: TaskId
    ) -> None:
        logger.debug("%s: %.2f %s", task_id, percent, message)

    async with periodic_task_result(
        Client(
            app=initialized_app,
            async_client=director_v2_client,
            base_url=TypeAdapter(AnyHttpUrl).validate_python(
                f"{director_v2_client.base_url}"
            ),
        ),
        task_id,
        task_timeout=60,
        status_poll_interval=1,
        progress_callback=_debug_progress_callback,
    ) as result:
        logger.debug("Task %s finished", task_id)
        return result


async def _assert_retrieve_completed(
    director_v2_client: httpx.AsyncClient,
    service_uuid: str,
    dynamic_services_urls: dict[str, str],
) -> None:
    await assert_retrieve_service(
        director_v2_client=director_v2_client,
        service_uuid=service_uuid,
    )

    container_id = await _container_id_via_services(service_uuid)

    # look at dynamic-sidecar's logs to be sure when nodeports
    # have been uploaded
    async with aiodocker.Docker() as docker_client:
        async for attempt in AsyncRetrying(
            reraise=True,
            retry=retry_if_exception_type(AssertionError),
            stop=stop_after_delay(TIMEOUT_OUTPUTS_UPLOAD_FINISH_DETECTED),
            wait=wait_fixed(0.5),
        ):
            with attempt:
                print(
                    f"--> checking container logs of {service_uuid=}, [attempt {attempt.retry_state.attempt_number}]..."
                )
                container: DockerContainer = await docker_client.containers.get(
                    container_id
                )

                logs = " ".join(
                    await cast(
                        Coroutine[Any, Any, list[str]],
                        container.log(stdout=True, stderr=True),
                    )
                )
                assert (
                    _CONTROL_TESTMARK_DY_SIDECAR_NODEPORT_UPLOADED_MESSAGE in logs
                ), "TIP: Message missing suggests that the data was never uploaded: look in services/dynamic-sidecar/src/simcore_service_dynamic_sidecar/modules/nodeports.py"


@pytest.mark.flaky(max_runs=3)
async def test_nodeports_integration(
    cleanup_services_and_networks: None,
    projects_networks_db: None,
    mocked_service_awaits_manual_interventions: None,
    mock_resource_usage_tracker: None,
    mock_osparc_variables_api_auth_rpc: None,
    initialized_app: FastAPI,
    update_project_workbench_with_comp_tasks: Callable,
    async_client: httpx.AsyncClient,
    db_manager: DBManager,
    current_user: dict[str, Any],
    current_study: ProjectAtDB,
    services_endpoint: dict[str, URL],
    workbench_dynamic_services: dict[str, Node],
    services_node_uuids: ServicesNodeUUIDs,
    fake_dy_success: dict[str, Any],
    tmp_path: Path,
    osparc_product_name: str,
    create_pipeline: Callable[..., Awaitable[ComputationGet]],
    mock_io_log_redirect_cb: LogRedirectCB,
    faker: Faker,
) -> None:
    """
    Creates a new project with where the following connections
    are defined: `sleeper:1.0.0` ->
    `dy-static-file-server-dynamic-sidecar:2.0.0` ->
    `dy-static-file-server-dynamic-sidecar-compose-spec:2.0.0`.

    Both `dy-static-file-server-*` services are able to map the
    inputs of the service to the outputs. Both services also
    generate an internal state which is to be persisted
    between runs.

    Execution steps:
    1. start all the dynamic services and make sure they are runningv2/dynamic_services'
    2. run the computational pipeline & trigger port retrievals
    3. check that the outputs of the `sleeper` are the same as the
        outputs of the `dy-static-file-server-dynamic-sidecar-compose-spec``
    4. fetch the "state" via `docker/aioboto` for both dynamic services
    5. start the dynamic-services and fetch the "state" via
        `storage-data_manager API/aioboto` for both dynamic services
    6. start the dynamic-services again, fetch the "state" via
        `docker/aioboto` for both dynamic services
    7. finally check that all states for both dynamic services match

    NOTE: when the services are started using S3 as a backend
    for saving the state, the state files are recovered via
    `aioboto` instead of `docker` or `storage-data_manager API`.
    """
    # STEP 1
    dynamic_services_urls: dict[
        str, str
    ] = await _start_and_wait_for_dynamic_services_ready(
        director_v2_client=async_client,
        product_name=osparc_product_name,
        user_id=current_user["id"],
        workbench_dynamic_services=workbench_dynamic_services,
        current_study=current_study,
        catalog_url=services_endpoint["catalog"],
    )

    # STEP 2
    task_out = await create_pipeline(
        async_client,
        project=current_study,
        user_id=current_user["id"],
        start_pipeline=True,
        product_name=osparc_product_name,
    )

    # wait for the computation to finish (either by failing, success or abort)
    task_out = await assert_and_wait_for_pipeline_status(
        async_client, task_out.url, current_user["id"], current_study.uuid
    )

    await assert_computation_task_out_obj(
        task_out,
        project=current_study,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=PipelineDetails.model_validate(fake_dy_success),
        iteration=1,
        cluster_id=DEFAULT_CLUSTER_ID,
    )
    update_project_workbench_with_comp_tasks(str(current_study.uuid))

    # STEP 3

    # Trigger inputs pulling & outputs pushing on dynamic services
    # Since there is no webserver monitoring postgres notifications
    # trigger the call manually

    # NOTE: the order of these services is important since
    # the outputs for `services_node_uuids.dy` needs to end up in
    # the inputs for `services_node_uuids.dy_compose_spec`
    for service_uuid in (services_node_uuids.dy, services_node_uuids.dy_compose_spec):
        # when retrieving inputs, only file output ports will be uploaded
        await _assert_retrieve_completed(
            director_v2_client=async_client,
            service_uuid=service_uuid,
            dynamic_services_urls=dynamic_services_urls,
        )

        # Wait for file ports to propagate
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5), wait=wait_fixed(1)
        ):
            with attempt:
                await _assert_port_values(
                    current_user["id"],
                    current_study,
                    db_manager,
                    services_node_uuids,
                    only_files=True,
                    include_dy_compose_spec=service_uuid
                    == services_node_uuids.dy_compose_spec,
                )

        # this will cause non files to upload
        await _assert_push_non_file_outputs(
            initialized_app=initialized_app,
            director_v2_client=async_client,
            service_uuid=service_uuid,
        )

        # Waiting for NON file ports to propagate
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5), wait=wait_fixed(1)
        ):
            with attempt:
                await _assert_port_values(
                    current_user["id"],
                    current_study,
                    db_manager,
                    services_node_uuids,
                    only_files=False,
                    include_dy_compose_spec=service_uuid
                    == services_node_uuids.dy_compose_spec,
                )

    # STEP 4

    app_settings: AppSettings = async_client._transport.app.state.settings  # type: ignore
    r_clone_settings: RCloneSettings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_R_CLONE_SETTINGS
    )

    if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
        await sleep_for(
            WAIT_FOR_R_CLONE_VOLUME_TO_SYNC_DATA,
            "Waiting for rclone to sync data from the docker volume",
        )

    dy_path_volume_before = (
        await _fetch_data_via_aioboto(
            r_clone_settings=r_clone_settings,
            dir_tag="dy",
            temp_dir=tmp_path,
            node_id=services_node_uuids.dy,
            project_id=current_study.uuid,
        )
        if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED
        else await _fetch_data_from_container(
            dir_tag="dy", service_uuid=services_node_uuids.dy, temp_dir=tmp_path
        )
    )
    dy_compose_spec_path_volume_before = (
        await _fetch_data_via_aioboto(
            r_clone_settings=r_clone_settings,
            dir_tag="dy_compose_spec",
            temp_dir=tmp_path,
            node_id=services_node_uuids.dy_compose_spec,
            project_id=current_study.uuid,
        )
        if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED
        else await _fetch_data_from_container(
            dir_tag="dy_compose_spec",
            service_uuid=services_node_uuids.dy_compose_spec,
            temp_dir=tmp_path,
        )
    )

    # STEP 5

    # stop the services to make sure the data is saved to storage
    await asyncio.gather(
        *(
            assert_stop_service(
                director_v2_client=async_client,
                service_uuid=service_uuid,
            )
            for service_uuid in workbench_dynamic_services
        )
    )

    await _wait_for_dy_services_to_fully_stop(async_client)

    if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
        await sleep_for(
            WAIT_FOR_R_CLONE_VOLUME_TO_SYNC_DATA,
            "Waiting for rclone to sync data from the docker volume",
        )

    dy_path_data_manager_before = (
        await _fetch_data_via_aioboto(
            r_clone_settings=r_clone_settings,
            dir_tag="dy",
            temp_dir=tmp_path,
            node_id=services_node_uuids.dy,
            project_id=current_study.uuid,
        )
        if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED
        else await _fetch_data_via_data_manager(
            r_clone_settings=r_clone_settings,
            dir_tag="dy",
            user_id=current_user["id"],
            project_id=current_study.uuid,
            service_uuid=NodeID(services_node_uuids.dy),
            temp_dir=tmp_path,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            faker=faker,
        )
    )

    dy_compose_spec_path_data_manager_before = (
        await _fetch_data_via_aioboto(
            r_clone_settings=r_clone_settings,
            dir_tag="dy_compose_spec",
            temp_dir=tmp_path,
            node_id=services_node_uuids.dy_compose_spec,
            project_id=current_study.uuid,
        )
        if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED
        else await _fetch_data_via_data_manager(
            r_clone_settings=r_clone_settings,
            dir_tag="dy_compose_spec",
            user_id=current_user["id"],
            project_id=current_study.uuid,
            service_uuid=NodeID(services_node_uuids.dy_compose_spec),
            temp_dir=tmp_path,
            io_log_redirect_cb=mock_io_log_redirect_cb,
            faker=faker,
        )
    )

    # STEP 6

    await _start_and_wait_for_dynamic_services_ready(
        director_v2_client=async_client,
        product_name=osparc_product_name,
        user_id=current_user["id"],
        workbench_dynamic_services=workbench_dynamic_services,
        current_study=current_study,
        catalog_url=services_endpoint["catalog"],
    )

    dy_path_volume_after = (
        await _fetch_data_via_aioboto(
            r_clone_settings=r_clone_settings,
            dir_tag="dy",
            temp_dir=tmp_path,
            node_id=services_node_uuids.dy,
            project_id=current_study.uuid,
        )
        if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED
        else await _fetch_data_from_container(
            dir_tag="dy", service_uuid=services_node_uuids.dy, temp_dir=tmp_path
        )
    )
    dy_compose_spec_path_volume_after = (
        await _fetch_data_via_aioboto(
            r_clone_settings=r_clone_settings,
            dir_tag="dy_compose_spec",
            temp_dir=tmp_path,
            node_id=services_node_uuids.dy_compose_spec,
            project_id=current_study.uuid,
        )
        if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED
        else await _fetch_data_from_container(
            dir_tag="dy_compose_spec",
            service_uuid=services_node_uuids.dy_compose_spec,
            temp_dir=tmp_path,
        )
    )

    # STEP 7

    _assert_same_set(
        _get_file_hashes_in_path(dy_path_volume_before),
        _get_file_hashes_in_path(dy_path_data_manager_before),
        _get_file_hashes_in_path(dy_path_volume_after),
    )

    _assert_same_set(
        _get_file_hashes_in_path(dy_compose_spec_path_volume_before),
        _get_file_hashes_in_path(dy_compose_spec_path_data_manager_before),
        _get_file_hashes_in_path(dy_compose_spec_path_volume_after),
    )
