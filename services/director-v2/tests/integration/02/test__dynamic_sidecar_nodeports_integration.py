# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import hashlib
import json
import logging
import os
from asyncio import BaseEventLoop
from collections import namedtuple
from itertools import tee
from pathlib import Path
from pprint import pformat
from typing import (
    Any,
    AsyncIterable,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Set,
    Tuple,
    cast,
)
from uuid import uuid4

import aiodocker
import aiopg.sa
import httpx
import pytest
import sqlalchemy as sa
from _pytest.monkeypatch import MonkeyPatch
from aiodocker.containers import DockerContainer
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from models_library.projects import Node, ProjectAtDB, Workbench
from models_library.projects_pipeline import PipelineDetails
from models_library.projects_state import RunningState
from models_library.settings.rabbit import RabbitConfig
from models_library.settings.redis import RedisConfig
from py._path.local import LocalPath
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.utils_docker import get_ip
from shared_comp_utils import (
    assert_computation_task_out_obj,
    assert_pipeline_status,
    create_pipeline,
)
from simcore_postgres_database.models.comp_pipeline import comp_pipeline
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_sdk import node_ports_v2
from simcore_sdk.node_data import data_manager

# FIXTURES
from simcore_sdk.node_ports_common import config as node_ports_config
from simcore_sdk.node_ports_v2 import DBManager, Nodeports, Port
from simcore_service_director_v2.core.application import init_app
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.schemas.comp_tasks import ComputationTaskOut
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from starlette import status
from starlette.testclient import TestClient
from utils import (
    SEPARATOR,
    assert_all_services_running,
    assert_retrieve_service,
    assert_services_reply_200,
    assert_start_service,
    assert_stop_service,
    ensure_network_cleanup,
    is_legacy,
    patch_dynamic_service_url,
)
from yarl import URL

pytest_simcore_core_services_selection = [
    "catalog",
    "dask-scheduler",
    "dask-sidecar",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "adminer",
    "minio",
]


ServicesNodeUUIDs = namedtuple("ServicesNodeUUIDs", "sleeper, dy, dy_compose_spec")
InputsOutputs = namedtuple("InputsOutputs", "inputs, outputs")

DY_SERVICES_STATE_PATH: Path = Path("/dy-volumes/workdir_generated-data")
TIMEOUT_DETECT_DYNAMIC_SERVICES_STOPPED = 60
TIMEOUT_OUTPUTS_UPLOAD_FINISH_DETECTED = 60
POSSIBLE_ISSUE_WORKAROUND = 10


logger = logging.getLogger(__name__)


@pytest.fixture
def minimal_configuration(  # pylint:disable=too-many-arguments
    sleeper_service: Dict,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: Dict,
    redis_service: RedisConfig,
    postgres_db: sa.engine.Engine,
    postgres_host_config: Dict[str, str],
    rabbit_service: RabbitConfig,
    simcore_services_ready: None,
    storage_service: URL,
    dask_scheduler_service: None,
    dask_sidecar_service: None,
    ensure_swarm_and_networks: None,
) -> Iterator[None]:
    node_ports_config.STORAGE_ENDPOINT = (
        f"{storage_service.host}:{storage_service.port}"
    )
    with postgres_db.connect() as conn:
        # pylint: disable=no-value-for-parameter
        conn.execute(comp_tasks.delete())
        conn.execute(comp_pipeline.delete())
        yield


@pytest.fixture
def fake_dy_workbench(
    mocks_dir: Path,
    sleeper_service: Dict,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: Dict,
) -> Dict[str, Any]:
    dy_workbench_template = mocks_dir / "fake_dy_workbench_template.json"
    assert dy_workbench_template.exists()

    file_content = dy_workbench_template.read_text()
    file_as_dict = json.loads(file_content)

    def _assert_version(registry_service_data: Dict) -> None:
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
def fake_dy_success(mocks_dir: Path) -> Dict[str, Any]:
    fake_dy_status_success = mocks_dir / "fake_dy_status_success.json"
    assert fake_dy_status_success.exists()
    return json.loads(fake_dy_status_success.read_text())


@pytest.fixture
def fake_dy_published(mocks_dir: Path) -> Dict[str, Any]:
    fake_dy_status_published = mocks_dir / "fake_dy_status_published.json"
    assert fake_dy_status_published.exists()
    return json.loads(fake_dy_status_published.read_text())


@pytest.fixture
def services_node_uuids(
    fake_dy_workbench: Dict[str, Any],
    sleeper_service: Dict,
    dy_static_file_server_dynamic_sidecar_service: Dict,
    dy_static_file_server_dynamic_sidecar_compose_spec_service: Dict,
) -> ServicesNodeUUIDs:
    def _get_node_uuid(registry_service_data: Dict) -> str:
        key = registry_service_data["schema"]["key"]
        version = registry_service_data["schema"]["version"]

        for node_uuid, workbench_service_data in fake_dy_workbench.items():
            if (
                workbench_service_data["key"] == key
                and workbench_service_data["version"] == version
            ):
                return node_uuid

        assert False, f"No node_uuid found for {key}:{version}"

    return ServicesNodeUUIDs(
        sleeper=_get_node_uuid(sleeper_service),
        dy=_get_node_uuid(dy_static_file_server_dynamic_sidecar_service),
        dy_compose_spec=_get_node_uuid(
            dy_static_file_server_dynamic_sidecar_compose_spec_service
        ),
    )


@pytest.fixture
def current_study(project: Callable, fake_dy_workbench: Dict[str, Any]) -> ProjectAtDB:
    return project(workbench=fake_dy_workbench)


@pytest.fixture
def workbench_dynamic_services(
    current_study: ProjectAtDB, sleeper_service: Dict
) -> Dict[str, Node]:
    sleeper_key = sleeper_service["schema"]["key"]
    result = {k: v for k, v in current_study.workbench.items() if v.key != sleeper_key}
    assert len(result) == 2
    return result


@pytest.fixture
async def db_manager(postgres_dsn: Dict[str, str]) -> AsyncIterable[DBManager]:
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn
    )
    async with aiopg.sa.create_engine(dsn) as db_engine:
        yield DBManager(db_engine)


@pytest.fixture
async def fast_api_app(
    minimal_configuration: None, network_name: str, monkeypatch: MonkeyPatch
) -> FastAPI:
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
    monkeypatch.setenv("DYNAMIC_SIDECAR_TRAEFIK_ACCESS_LOG", "true")
    monkeypatch.setenv("DYNAMIC_SIDECAR_TRAEFIK_LOGLEVEL", "debug")
    # patch host for dynamic-sidecar, not reachable via localhost
    # the dynamic-sidecar (running inside a container) will use
    # this address to reach the rabbit service
    monkeypatch.setenv("RABBIT_HOST", f"{get_ip()}")

    settings = AppSettings.create_from_envs()

    app = init_app(settings)
    return app


@pytest.fixture
async def director_v2_client(
    loop: BaseEventLoop, fast_api_app: FastAPI
) -> AsyncIterable[httpx.AsyncClient]:
    async with LifespanManager(fast_api_app):
        async with httpx.AsyncClient(
            app=fast_api_app, base_url="http://testserver/v2"
        ) as client:
            yield client


@pytest.fixture
def client(fast_api_app: FastAPI) -> TestClient:
    """required to avoid rewriting existing code"""
    return TestClient(fast_api_app, raise_server_exceptions=True)


@pytest.fixture
async def cleanup_services_and_networks(
    workbench_dynamic_services: Dict[str, Node],
    current_study: ProjectAtDB,
    director_v2_client: httpx.AsyncClient,
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

        # pylint: disable=protected-access
        scheduler_interval = (
            director_v2_client._transport.app.state.settings.DYNAMIC_SERVICES.DYNAMIC_SCHEDULER.DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS
        )
        # sleep enough to ensure the observation cycle properly stopped the service
        await asyncio.sleep(2 * scheduler_interval)
        await ensure_network_cleanup(docker_client, project_id)


@pytest.fixture
def temp_dir(tmpdir: LocalPath) -> Path:
    return Path(tmpdir)


# UTILS


async def _get_mapped_nodeports_values(
    user_id: int, project_id: str, workbench: Workbench, db_manager: DBManager
) -> Dict[str, InputsOutputs]:
    result: Dict[str, InputsOutputs] = {}

    for node_uuid in workbench:
        PORTS: Nodeports = await node_ports_v2.ports(
            user_id=user_id,
            project_id=project_id,
            node_uuid=str(node_uuid),
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
    mapped: Dict[str, InputsOutputs],
    services_node_uuids: ServicesNodeUUIDs,
):
    print("Nodeport mapped values")
    for node_uuid, inputs_outputs in mapped.items():
        print("Port values for", node_uuid)
        print("INPUTS")
        for value in inputs_outputs.inputs.values():
            print(value.key, value)
        print("OUTPUTS")
        for value in inputs_outputs.outputs.values():
            print(value.key, value)

    # integer values
    sleeper_out_2 = await mapped[services_node_uuids.sleeper].outputs["out_2"].get()
    dy_integer_intput = (
        await mapped[services_node_uuids.dy].inputs["integer_input"].get()
    )
    dy_integer_output = (
        await mapped[services_node_uuids.dy].outputs["integer_output"].get()
    )

    dy_compose_spec_integer_intput = (
        await mapped[services_node_uuids.dy_compose_spec].inputs["integer_input"].get()
    )
    dy_compose_spec_integer_output = (
        await mapped[services_node_uuids.dy_compose_spec]
        .outputs["integer_output"]
        .get()
    )

    _print_values_to_assert(
        sleeper_out_2=sleeper_out_2,
        dy_integer_intput=dy_integer_intput,
        dy_integer_output=dy_integer_output,
        dy_compose_spec_integer_intput=dy_compose_spec_integer_intput,
        dy_compose_spec_integer_output=dy_compose_spec_integer_output,
    )

    assert sleeper_out_2 == dy_integer_intput
    assert sleeper_out_2 == dy_integer_output
    assert sleeper_out_2 == dy_compose_spec_integer_intput
    assert sleeper_out_2 == dy_compose_spec_integer_output

    # files

    async def _int_value_port(port: Port) -> int:
        file_path: Path = cast(Path, await port.get())
        int_value = int(file_path.read_text())
        return int_value

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
    assert sleeper_out_1 == dy_compose_spec_file_input
    assert sleeper_out_1 == dy_compose_spec_file_output


def _patch_postgres_address(director_v2_client: httpx.AsyncClient) -> None:
    # the dynamic-sidecar cannot reach postgres via port
    # forwarding to localhost. the docker postgres host must be used

    # pylint: disable=protected-access
    director_v2_client._transport.app.state.settings.POSTGRES.__config__.allow_mutation = (
        True
    )
    director_v2_client._transport.app.state.settings.POSTGRES.__config__.frozen = False
    director_v2_client._transport.app.state.settings.POSTGRES.POSTGRES_HOST = "postgres"


def _assert_command_successful(command: str) -> None:
    print(command)
    assert os.system(command) == 0


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

    _assert_command_successful(
        f"docker cp {container_id}:/{DY_SERVICES_STATE_PATH}/. {target_path}"
    )

    return target_path


async def _fetch_data_via_data_manager(
    dir_tag: str, user_id: int, project_id: str, service_uuid: str, temp_dir: Path
) -> Path:
    save_to = temp_dir / f"data-manager_{dir_tag}_{uuid4()}"
    save_to.mkdir(parents=True, exist_ok=True)

    assert (
        await data_manager.is_file_present_in_storage(
            user_id=user_id,
            project_id=project_id,
            node_uuid=service_uuid,
            file_path=DY_SERVICES_STATE_PATH,
        )
        is True
    )

    await data_manager.pull(
        user_id=user_id,
        project_id=project_id,
        node_uuid=service_uuid,
        file_or_folder=DY_SERVICES_STATE_PATH,
        save_to=save_to,
    )

    return save_to


async def _wait_for_dynamic_services_to_be_running(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    user_id: int,
    workbench_dynamic_services: Dict[str, Node],
    current_study: ProjectAtDB,
) -> Dict[str, str]:
    # start dynamic services
    await asyncio.gather(
        *(
            assert_start_service(
                director_v2_client=director_v2_client,
                user_id=user_id,
                project_id=str(current_study.uuid),
                service_key=node.key,
                service_version=node.version,
                service_uuid=service_uuid,
                basepath=f"/x/{service_uuid}" if is_legacy(node) else None,
            )
            for service_uuid, node in workbench_dynamic_services.items()
        )
    )

    dynamic_services_urls: Dict[str, str] = {}

    for service_uuid in workbench_dynamic_services:
        dynamic_service_url = await patch_dynamic_service_url(
            # pylint: disable=protected-access
            app=director_v2_client._transport.app,
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
    to_observe = (
        director_v2_client._transport.app.state.dynamic_sidecar_scheduler._to_observe
    )

    for i in range(TIMEOUT_DETECT_DYNAMIC_SERVICES_STOPPED):
        print(
            (
                f"Sleeping for {i+1}/{TIMEOUT_DETECT_DYNAMIC_SERVICES_STOPPED} "
                "seconds while waiting for removal of all dynamic-sidecars"
            )
        )
        await asyncio.sleep(1)
        if len(to_observe) == 0:
            break

        if i == TIMEOUT_DETECT_DYNAMIC_SERVICES_STOPPED - 1:
            assert False, "Timeout reached"


def _pairwise(iterable) -> Iterable[Tuple[Any, Any]]:
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def _assert_same_set(*sets_to_compare: Set[Any]) -> None:
    for first, second in _pairwise(sets_to_compare):
        assert first == second


def _get_file_hashes_in_path(path_to_hash: Path) -> Set[Tuple[Path, str]]:
    def _hash_path(path: Path):
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
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


LINE_PARTS_TO_MATCH = [
    (0, "INFO:simcore_service_dynamic_sidecar.modules.nodeports:Uploaded"),
    (2, "bytes"),
    (3, "in"),
    (5, "seconds"),
]


def _is_matching_line_in_logs(logs: List[str]) -> bool:
    for line in logs:
        if LINE_PARTS_TO_MATCH[0][1] in line:
            print("".join(logs))

            line_parts = line.strip().split(" ")
            for position, value in LINE_PARTS_TO_MATCH:
                assert line_parts[position] == value

            return True
    return False


async def _print_dynamic_sidecars_containers_logs_and_get_containers(
    dynamic_services_urls: Dict[str, str]
) -> List[str]:
    containers_names: List[str] = []
    for node_uuid, url in dynamic_services_urls.items():
        print(f"Containers logs for service {node_uuid} @ {url}")
        async with httpx.AsyncClient(base_url=f"{url}/v1") as client:
            containers_inspect_response = await client.get("/containers")
            assert (
                containers_inspect_response.status_code == status.HTTP_200_OK
            ), containers_inspect_response.text
            containers_inspect = containers_inspect_response.json()

            # pylint: disable=unnecessary-comprehension
            service_containers_names = [x for x in containers_inspect]
            print("Containers:", service_containers_names)
            for container_name in service_containers_names:
                containers_names.append(container_name)
                print(f"Fetching logs for {container_name}")
                container_logs_response = await client.get(
                    f"/containers/{container_name}/logs"
                )
                assert container_logs_response.status_code == status.HTTP_200_OK
                logs = "".join(container_logs_response.json())
                print(f"Container {container_name} logs:\n{logs}")

    assert len(containers_names) == 3
    return containers_names


async def _print_container_inspect(container_id: str) -> None:
    async with aiodocker.Docker() as docker_client:
        container = await docker_client.containers.get(container_id)
        container_inspect = await container.show()
        print(f"Container {container_id} inspect:\n{pformat(container_inspect)}")


async def _print_all_docker_volumes() -> None:
    async with aiodocker.Docker() as docker_client:
        docker_volumes = await docker_client.volumes.list()
        print(f"Detected volumes:\n{pformat(docker_volumes)}")


async def _assert_retrieve_completed(
    director_v2_client: httpx.AsyncClient,
    director_v0_url: URL,
    service_uuid: str,
    dynamic_services_urls: Dict[str, str],
) -> None:
    await assert_retrieve_service(
        director_v2_client=director_v2_client,
        service_uuid=service_uuid,
    )

    container_id = await _container_id_via_services(service_uuid)

    # look at dynamic-sidecar's logs to be sure when nodeports
    # have been uploaded
    async with aiodocker.Docker() as docker_client:
        container: DockerContainer = await docker_client.containers.get(container_id)

        for i in range(TIMEOUT_OUTPUTS_UPLOAD_FINISH_DETECTED):
            logs = await container.log(stdout=True, stderr=True)

            if _is_matching_line_in_logs(logs):
                break

            if i == TIMEOUT_OUTPUTS_UPLOAD_FINISH_DETECTED - 1:
                print(SEPARATOR)
                print(f"Dumping information for service_uuid={service_uuid}")
                print(SEPARATOR)

                print("".join(logs))
                print(SEPARATOR)

                containers_names = (
                    await _print_dynamic_sidecars_containers_logs_and_get_containers(
                        dynamic_services_urls
                    )
                )
                print(SEPARATOR)

                # inspect dynamic-sidecar container
                await _print_container_inspect(container_id=container_id)
                print(SEPARATOR)

                # inspect spawned container
                for container_name in containers_names:
                    await _print_container_inspect(container_id=container_name)
                    print(SEPARATOR)

                await _print_all_docker_volumes()
                print(SEPARATOR)

                assert False, "Timeout reached"

            print(
                (
                    f"Sleeping {i+1}/{TIMEOUT_OUTPUTS_UPLOAD_FINISH_DETECTED} "
                    f"before searching logs from {service_uuid} again"
                )
            )
            await asyncio.sleep(1)

        print(f"Nodeports outputs upload finish detected for {service_uuid}")


# TESTS


async def test_nodeports_integration(
    # pylint: disable=too-many-arguments
    minimal_configuration: None,
    cleanup_services_and_networks: None,
    update_project_workbench_with_comp_tasks: Callable,
    client: TestClient,
    db_manager: DBManager,
    user_db: Dict,
    current_study: ProjectAtDB,
    services_endpoint: Dict[str, URL],
    director_v2_client: httpx.AsyncClient,
    workbench_dynamic_services: Dict[str, Node],
    services_node_uuids: ServicesNodeUUIDs,
    fake_dy_success: Dict[str, Any],
    fake_dy_published: Dict[str, Any],
    temp_dir: Path,
    mocker: MockerFixture,
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
    1. start all the dynamic services and make sure they are running
    2. run the computational pipeline & trigger port retrievals
    3. check that the outputs of the `sleeper` are the same as the
        outputs of the `dy-static-file-server-dynamic-sidecar-compose-spec``
    4. fetch the "state" via `docker ` for both dynamic services
    5. start the dynamic-services and fetch the "state" via
        `storage-data_manager API` for both dynamic services
    6. start the dynamic-services again, fetch the "state" via
        `docker` for both dynamic services
    7. finally check that all states for both dynamic services match
    """

    # STEP 1

    _patch_postgres_address(director_v2_client)

    dynamic_services_urls: Dict[
        str, str
    ] = await _wait_for_dynamic_services_to_be_running(
        director_v2_client=director_v2_client,
        director_v0_url=services_endpoint["director"],
        user_id=user_db["id"],
        workbench_dynamic_services=workbench_dynamic_services,
        current_study=current_study,
    )

    # STEP 2

    response = create_pipeline(
        client,
        project=current_study,
        user_id=user_db["id"],
        start_pipeline=True,
        expected_response_status_code=status.HTTP_201_CREATED,
    )
    task_out = ComputationTaskOut.parse_obj(response.json())

    # check the contents is correct: a pipeline that just started gets PUBLISHED
    assert_computation_task_out_obj(
        client,
        task_out,
        project=current_study,
        exp_task_state=RunningState.PUBLISHED,
        exp_pipeline_details=PipelineDetails.parse_obj(fake_dy_published),
    )

    # wait for the computation to start
    assert_pipeline_status(
        client,
        task_out.url,
        user_db["id"],
        current_study.uuid,
        wait_for_states=[RunningState.STARTED],
    )

    # wait for the computation to finish (either by failing, success or abort)
    task_out = assert_pipeline_status(
        client, task_out.url, user_db["id"], current_study.uuid
    )

    assert_computation_task_out_obj(
        client,
        task_out,
        project=current_study,
        exp_task_state=RunningState.SUCCESS,
        exp_pipeline_details=PipelineDetails.parse_obj(fake_dy_success),
    )

    update_project_workbench_with_comp_tasks(str(current_study.uuid))

    # Trigger inputs pulling & outputs pushing on dynamic services

    # Since there is no webserver monitoring postgres notifications
    # trigger the call manually

    # dump logs form started containers before retrieve
    await _print_dynamic_sidecars_containers_logs_and_get_containers(
        dynamic_services_urls
    )

    await _assert_retrieve_completed(
        director_v2_client=director_v2_client,
        director_v0_url=services_endpoint["director"],
        service_uuid=services_node_uuids.dy,
        dynamic_services_urls=dynamic_services_urls,
    )

    await _assert_retrieve_completed(
        director_v2_client=director_v2_client,
        director_v0_url=services_endpoint["director"],
        service_uuid=services_node_uuids.dy_compose_spec,
        dynamic_services_urls=dynamic_services_urls,
    )

    # STEP 3
    # pull data via nodeports

    # storage config.py resolves env vars at import time, unlike newer settingslib
    # configuration. patching the module with the correct url
    mocker.patch(
        "simcore_sdk.node_ports_common.config.STORAGE_ENDPOINT",
        str(services_endpoint["storage"]).replace("http://", ""),
    )

    mapped_nodeports_values = await _get_mapped_nodeports_values(
        user_db["id"], str(current_study.uuid), current_study.workbench, db_manager
    )
    await _assert_port_values(mapped_nodeports_values, services_node_uuids)

    # STEP 4

    dy_path_container_before = await _fetch_data_from_container(
        dir_tag="dy", service_uuid=services_node_uuids.dy, temp_dir=temp_dir
    )
    dy_compose_spec_path_container_before = await _fetch_data_from_container(
        dir_tag="dy_compose_spec",
        service_uuid=services_node_uuids.dy_compose_spec,
        temp_dir=temp_dir,
    )

    # STEP 5

    # stop the services to make sure the data is saved to storage
    await asyncio.gather(
        *(
            assert_stop_service(
                director_v2_client=director_v2_client,
                service_uuid=service_uuid,
            )
            for service_uuid in workbench_dynamic_services
        )
    )

    await _wait_for_dy_services_to_fully_stop(director_v2_client)

    dy_path_data_manager_before = await _fetch_data_via_data_manager(
        dir_tag="dy",
        user_id=user_db["id"],
        project_id=str(current_study.uuid),
        service_uuid=services_node_uuids.dy,
        temp_dir=temp_dir,
    )

    dy_compose_spec_path_data_manager_before = await _fetch_data_via_data_manager(
        dir_tag="dy_compose_spec",
        user_id=user_db["id"],
        project_id=str(current_study.uuid),
        service_uuid=services_node_uuids.dy_compose_spec,
        temp_dir=temp_dir,
    )

    # STEP 6

    await _wait_for_dynamic_services_to_be_running(
        director_v2_client=director_v2_client,
        director_v0_url=services_endpoint["director"],
        user_id=user_db["id"],
        workbench_dynamic_services=workbench_dynamic_services,
        current_study=current_study,
    )

    dy_path_container_after = await _fetch_data_from_container(
        dir_tag="dy", service_uuid=services_node_uuids.dy, temp_dir=temp_dir
    )
    dy_compose_spec_path_container_after = await _fetch_data_from_container(
        dir_tag="dy_compose_spec",
        service_uuid=services_node_uuids.dy_compose_spec,
        temp_dir=temp_dir,
    )

    # STEP 7

    _assert_same_set(
        _get_file_hashes_in_path(dy_path_container_before),
        _get_file_hashes_in_path(dy_path_data_manager_before),
        _get_file_hashes_in_path(dy_path_container_after),
    )

    _assert_same_set(
        _get_file_hashes_in_path(dy_compose_spec_path_container_before),
        _get_file_hashes_in_path(dy_compose_spec_path_data_manager_before),
        _get_file_hashes_in_path(dy_compose_spec_path_container_after),
    )
