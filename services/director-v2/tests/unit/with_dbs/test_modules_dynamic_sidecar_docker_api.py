# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
import contextlib
import datetime
import logging
import sys
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import aiodocker
import pytest
from aiodocker.utils import clean_filters
from aiodocker.volumes import DockerVolume
from faker import Faker
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_directorv2.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
    DYNAMIC_VOLUME_REMOVER_PREFIX,
)
from models_library.api_schemas_directorv2.dynamic_services_scheduler import (
    DockerContainerInspect,
    SimcoreServiceLabels,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pytest_simcore.helpers.utils_envs import EnvVarsDict
from simcore_service_director_v2.core.settings import DynamicSidecarSettings
from simcore_service_director_v2.models.schemas.dynamic_services import (
    SchedulerData,
    ServiceState,
)
from simcore_service_director_v2.modules.dynamic_sidecar import docker_api
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api._core import (
    _update_service_spec,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api._utils import (
    docker_client,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.volume_remover import (
    DockerVersion,
    spec_volume_removal_service,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarError,
    GenericDockerError,
)
from tenacity import TryAgain
from tenacity._asyncio import AsyncRetrying
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

MAX_INT64 = sys.maxsize

logger = logging.getLogger(__name__)


pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def dynamic_sidecar_settings(
    monkeypatch: pytest.MonkeyPatch, mock_env: EnvVarsDict
) -> DynamicSidecarSettings:
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:MOCKED")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")
    return DynamicSidecarSettings.create_from_envs()


@pytest.fixture
def network_config(simcore_services_network_name: str, faker: Faker) -> dict[str, Any]:
    return {
        "Name": simcore_services_network_name,
        "Driver": "overlay",
        "Labels": {"uuid": f"{faker.uuid4()}"},
    }


@pytest.fixture
async def ensure_swarm_network(
    network_config: dict[str, Any],
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[None]:
    network_id = await docker_api.create_network(network_config)
    yield

    # docker containers must be gone before network removal is functional
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)
    ):
        with attempt:
            print(
                f"removing network with {network_id=}, attempt {attempt.retry_state.attempt_number}..."
            )
            docker_network = await async_docker_client.networks.get(network_id)
            assert await docker_network.delete() is True
            print(f"network with {network_id=} removed")


@pytest.fixture
async def cleanup_swarm_network(
    simcore_services_network_name: str,
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[None]:
    yield
    # docker containers must be gone before network removal is functional
    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(1), stop=stop_after_delay(60)
    ):
        with attempt:
            print(
                f"removing network with {simcore_services_network_name=}, attempt {attempt.retry_state.attempt_number}..."
            )
            docker_network = await async_docker_client.networks.get(
                simcore_services_network_name
            )
            assert await docker_network.delete() is True
            print(f"network with {simcore_services_network_name=} removed")


@pytest.fixture
def test_service_name(faker: Faker) -> str:
    return f"test_service_name_{faker.hostname(0)}"


@pytest.fixture
def service_spec(test_service_name: str) -> dict[str, Any]:
    # "joseluisq/static-web-server" is ~2MB docker image
    return {
        "name": test_service_name,
        "task_template": {"ContainerSpec": {"Image": "joseluisq/static-web-server"}},
        "labels": {"foo": "bar"},
    }


@pytest.fixture
async def cleanup_test_service_name(
    test_service_name: str,
    async_docker_client: aiodocker.Docker,
    docker_swarm: None,
) -> AsyncIterator[None]:
    yield

    assert await async_docker_client.services.delete(test_service_name) is True


@pytest.fixture
def dynamic_sidecar_service_name() -> str:
    return f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_some-dynamic-fake-sidecar"


@pytest.fixture
def dynamic_sidecar_service_spec(
    dynamic_sidecar_service_name: str,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    scheduler_data_from_http_request: SchedulerData,
) -> dict[str, Any]:
    # "joseluisq/static-web-server" is ~2MB docker image
    scheduler_data_from_http_request.service_name = dynamic_sidecar_service_name

    return {
        "name": dynamic_sidecar_service_name,
        "task_template": {"ContainerSpec": {"Image": "joseluisq/static-web-server"}},
        "labels": {
            "swarm_stack_name": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}",
            "uuid": f"{uuid4()}",
            "service_key": "simcore/services/dynamic/3dviewer",
            "service_tag": "2.4.5",
            "traefik.docker.network": "",
            "io.simcore.zone": "",
            "service_port": "80",
            "study_id": f"{uuid4()}",
            "user_id": "123",
            DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL: scheduler_data_from_http_request.json(),
        },
    }


@pytest.fixture
async def cleanup_test_dynamic_sidecar_service(
    dynamic_sidecar_service_name: str,
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[None]:
    yield
    assert (
        await async_docker_client.services.delete(dynamic_sidecar_service_name) is True
    )


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def node_uuid(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


@pytest.fixture
def dynamic_sidecar_stack_specs(
    node_uuid: UUID,
    user_id: UserID,
    project_id: ProjectID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> list[dict[str, Any]]:
    return [
        {
            "name": f"{DYNAMIC_PROXY_SERVICE_PREFIX}_fake_proxy",
            "task_template": {
                "ContainerSpec": {"Image": "joseluisq/static-web-server"}
            },
            "labels": {
                "swarm_stack_name": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}",
                "uuid": f"{node_uuid}",
                "user_id": f"{user_id}",
                "study_id": f"{project_id}",
            },
        },
        {
            "name": f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_fake_sidecar",
            "task_template": {
                "ContainerSpec": {"Image": "joseluisq/static-web-server"}
            },
            "labels": {
                "swarm_stack_name": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}",
                "uuid": f"{node_uuid}",
                "user_id": f"{user_id}",
                "study_id": f"{project_id}",
            },
        },
    ]


@pytest.fixture
async def cleanup_dynamic_sidecar_stack(
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    async_docker_client: aiodocker.Docker,
) -> AsyncIterator[None]:
    yield
    for dynamic_sidecar_spec in dynamic_sidecar_stack_specs:
        assert (
            await async_docker_client.services.delete(dynamic_sidecar_spec["name"])
            is True
        )


@pytest.fixture
async def project_id_labeled_network(
    async_docker_client: aiodocker.Docker, project_id: ProjectID
) -> AsyncIterable[str]:
    network_config = {
        "Name": "test_network_by_project_id",
        "Driver": "overlay",
        "Labels": {"project_id": f"{project_id}"},
    }
    network_id = await docker_api.create_network(network_config)

    yield network_id

    network = await async_docker_client.networks.get(network_id)
    assert await network.delete() is True


@pytest.fixture
async def test_networks(
    async_docker_client: aiodocker.Docker, docker_swarm: None
) -> AsyncIterator[list[str]]:
    network_names = [f"test_network_name__{k}" for k in range(5)]

    yield network_names

    for network_name in network_names:
        docker_network = await async_docker_client.networks.get(network_name)
        assert await docker_network.delete() is True


@pytest.fixture
async def existing_network(
    async_docker_client: aiodocker.Docker, project_id: ProjectID
) -> AsyncIterable[str]:
    name = "test_with_existing_network_by_project_id"
    network_config = {
        "Name": name,
        "Driver": "overlay",
        "Labels": {"project_id": f"{project_id}"},
    }
    network_id = await docker_api.create_network(network_config)

    yield name

    network = await async_docker_client.networks.get(network_id)
    assert await network.delete() is True


@pytest.fixture
def service_name() -> str:
    return "mock-service-name"


@pytest.fixture(
    params=[
        SimcoreServiceLabels.parse_obj(example)
        for example in SimcoreServiceLabels.Config.schema_extra["examples"]
    ],
)
def labels_example(request: pytest.FixtureRequest) -> SimcoreServiceLabels:
    return request.param


@pytest.fixture(params=[None, datetime.datetime.now(tz=datetime.timezone.utc)])
def time_dy_sidecar_became_unreachable(
    request: pytest.FixtureRequest,
) -> datetime.datetime | None:
    return request.param


@pytest.fixture
def mock_scheduler_data(
    labels_example: SimcoreServiceLabels,
    scheduler_data: SchedulerData,
    time_dy_sidecar_became_unreachable: datetime.datetime | None,
    service_name: str,
) -> SchedulerData:
    # test all possible cases
    if labels_example.paths_mapping is not None:
        scheduler_data.paths_mapping = labels_example.paths_mapping
    scheduler_data.compose_spec = labels_example.compose_spec
    scheduler_data.container_http_entry = labels_example.container_http_entry
    scheduler_data.restart_policy = labels_example.restart_policy

    scheduler_data.dynamic_sidecar.containers_inspect = [
        DockerContainerInspect.from_container(
            {"State": {"Status": "dead"}, "Name": "mock_name", "Id": "mock_id"}
        )
    ]
    scheduler_data.service_name = service_name
    return scheduler_data


@pytest.fixture
async def mock_service(
    async_docker_client: aiodocker.Docker, service_name: str
) -> AsyncIterable[str]:
    service_data = await async_docker_client.services.create(
        {"ContainerSpec": {"Image": "joseluisq/static-web-server:1.16.0-alpine"}},
        name=service_name,
    )

    yield service_name

    await async_docker_client.services.delete(service_data["ID"])


@pytest.mark.parametrize(
    "simcore_services_network_name",
    ("n", "network", "with_underscore", "with-dash", "with-dash_with_underscore"),
)
def test_settings__valid_network_names(
    simcore_services_network_name: str,
    monkeypatch: pytest.MonkeyPatch,
    dynamic_sidecar_settings: DynamicSidecarSettings,
) -> None:
    items = dynamic_sidecar_settings.dict()
    items["SIMCORE_SERVICES_NETWORK_NAME"] = simcore_services_network_name

    # validate network names
    DynamicSidecarSettings.parse_obj(items)


async def test_failed_docker_client_request(docker_swarm: None):
    missing_network_name = "this_network_cannot_be_found"

    with pytest.raises(GenericDockerError) as execinfo:
        async with docker_client() as client:
            await client.networks.get(missing_network_name)
    assert (
        str(execinfo.value)
        == f"Unexpected error from docker client: network {missing_network_name} not found"
    )


async def test_get_swarm_network_ok(
    dynamic_sidecar_settings: DynamicSidecarSettings,
    simcore_services_network_name: str,
    ensure_swarm_network: None,
    docker_swarm: None,
):
    swarm_network = await docker_api.get_swarm_network(dynamic_sidecar_settings)
    assert swarm_network["Name"] == simcore_services_network_name


async def test_get_swarm_network_missing_network(
    dynamic_sidecar_settings: DynamicSidecarSettings, docker_swarm: None
):
    with pytest.raises(DynamicSidecarError) as excinfo:
        await docker_api.get_swarm_network(dynamic_sidecar_settings)

    assert str(excinfo.value) == (
        "Swarm network name (searching for '*test_network_name*') is not configured."
        "Found following networks: []"
    )


async def test_recreate_network_multiple_times(
    network_config: dict[str, Any],
    cleanup_swarm_network: None,
    docker_swarm: None,
):
    network_ids = [await docker_api.create_network(network_config) for _ in range(10)]
    assert len(set(network_ids)) == 1, "expected same perh config"
    assert all(isinstance(nid, str) for nid in network_ids)


async def test_create_service(
    service_spec: dict[str, Any],
    cleanup_test_service_name: None,
    docker_swarm: None,
):
    service_id = await docker_api.create_service_and_get_id(service_spec)
    assert service_id


async def test_services_to_observe_exist(
    dynamic_sidecar_service_name: str,
    dynamic_sidecar_service_spec: dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
):
    service_id = await docker_api.create_service_and_get_id(
        dynamic_sidecar_service_spec
    )
    assert service_id

    dynamic_services = await docker_api.get_dynamic_sidecars_to_observe(
        dynamic_sidecar_settings
    )
    assert len(dynamic_services) == 1

    assert dynamic_services[0].service_name == dynamic_sidecar_service_name


async def test_dynamic_sidecar_in_running_state_and_node_id_is_recovered(
    dynamic_sidecar_service_spec: dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
):
    service_id = await docker_api.create_service_and_get_id(
        dynamic_sidecar_service_spec
    )
    assert service_id

    node_id = await docker_api.get_dynamic_sidecar_placement(
        service_id, dynamic_sidecar_settings
    )
    assert node_id

    # after the node_id is recovered the service
    # will be in a running state
    dynamic_sidecar_state = await docker_api.get_dynamic_sidecar_state(service_id)
    assert dynamic_sidecar_state == (ServiceState.RUNNING, "")


async def test_dynamic_sidecar_get_dynamic_sidecar_sate_fail_to_schedule(
    dynamic_sidecar_service_spec: dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
):
    # set unachievable resource
    dynamic_sidecar_service_spec["task_template"]["Resources"] = {
        "Reservations": {"NanoCPUs": MAX_INT64, "MemoryBytes": MAX_INT64}
    }

    service_id = await docker_api.create_service_and_get_id(
        dynamic_sidecar_service_spec
    )
    assert service_id

    # wait for the service to get scheduled
    await asyncio.sleep(0.2)

    dynamic_sidecar_state = await docker_api.get_dynamic_sidecar_state(service_id)
    assert dynamic_sidecar_state == (
        ServiceState.PENDING,
        "no suitable node (insufficient resources on 1 node)",
    )


async def test_is_dynamic_sidecar_stack_missing(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    services_are_missing = await docker_api.is_dynamic_sidecar_stack_missing(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing is True

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await docker_api.is_dynamic_sidecar_stack_missing(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing is False


async def test_are_sidecar_and_proxy_services_present(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    services_are_missing = await docker_api.are_sidecar_and_proxy_services_present(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing is False

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await docker_api.are_sidecar_and_proxy_services_present(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing is True


async def test_remove_dynamic_sidecar_stack(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
):
    async def _count_services_in_stack(
        node_uuid: UUID,
        dynamic_sidecar_settings: DynamicSidecarSettings,
        async_docker_client: aiodocker.Docker,
    ) -> int:
        services = await async_docker_client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
                    f"uuid={node_uuid}",
                ]
            }
        )
        return len(services)

    # ---------

    assert (
        await _count_services_in_stack(
            node_uuid, dynamic_sidecar_settings, async_docker_client
        )
        == 0
    )

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    assert (
        await _count_services_in_stack(
            node_uuid, dynamic_sidecar_settings, async_docker_client
        )
        == 2
    )

    await docker_api.remove_dynamic_sidecar_stack(node_uuid, dynamic_sidecar_settings)

    assert (
        await _count_services_in_stack(
            node_uuid, dynamic_sidecar_settings, async_docker_client
        )
        == 0
    )


async def test_remove_dynamic_sidecar_network(
    network_config: dict[str, Any],
    simcore_services_network_name: str,
    docker_swarm: None,
):
    network_ids = [await docker_api.create_network(network_config) for _ in range(10)]
    assert len(set(network_ids)) == 1

    delete_result = await docker_api.remove_dynamic_sidecar_network(
        simcore_services_network_name
    )
    assert delete_result is True


async def test_remove_dynamic_sidecar_network_fails(
    simcore_services_network_name: str, docker_swarm: None
):
    delete_result = await docker_api.remove_dynamic_sidecar_network(
        simcore_services_network_name
    )
    assert delete_result is False


async def test_is_sidecar_running(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    assert (
        await docker_api.is_sidecar_running(node_uuid, dynamic_sidecar_settings)
        is False
    )

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    async for attempt in AsyncRetrying(
        reraise=True, wait=wait_fixed(0.5), stop=stop_after_delay(10)
    ):
        with attempt:
            is_sidecar_running = await docker_api.is_sidecar_running(
                node_uuid, dynamic_sidecar_settings
            )
            print(f"Sidecar for service {node_uuid}: {is_sidecar_running=}")
            assert is_sidecar_running is True


async def test_get_projects_networks_containers(
    async_docker_client: aiodocker.Docker,
    project_id_labeled_network: str,
    project_id: ProjectID,
    docker_swarm: None,
):
    # make sure API does not change
    params = {"filters": clean_filters({"label": [f"project_id={project_id}"]})}
    filtered_networks = (
        # pylint:disable=protected-access
        await async_docker_client.networks.docker._query_json("networks", params=params)
    )
    assert len(filtered_networks) == 1
    filtered_network = filtered_networks[0]

    assert project_id_labeled_network == filtered_network["Id"]


async def test_get_or_create_networks_ids(
    test_networks: list[str], existing_network: str, project_id: ProjectID
):
    # test with duplicate networks and existing networks
    networks_to_test = (
        test_networks
        + test_networks
        + [
            existing_network,
        ]
    )
    network_ids = await docker_api.get_or_create_networks_ids(
        networks=networks_to_test,
        project_id=project_id,
    )
    assert set(networks_to_test) == set(network_ids.keys())


async def test_update_scheduler_data_label(
    async_docker_client: aiodocker.Docker,
    mock_service: str,
    mock_scheduler_data: SchedulerData,
    docker_swarm: None,
):
    await docker_api.update_scheduler_data_label(mock_scheduler_data)

    # fetch stored data in labels
    service_inspect = await async_docker_client.services.inspect(mock_service)
    labels = service_inspect["Spec"]["Labels"]
    scheduler_data = SchedulerData.parse_raw(
        labels[DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL]
    )
    assert scheduler_data == mock_scheduler_data


async def test_update_scheduler_data_label_skip_if_service_is_missing(
    async_docker_client: aiodocker.Docker, mock_scheduler_data: SchedulerData
):
    # NOTE: checks that docker engine replies with
    # `service mock-service-name not found`
    # the error is handled and that the error is not raised
    await docker_api.update_scheduler_data_label(mock_scheduler_data)


@pytest.mark.flaky(max_runs=3)
async def test_regression_update_service_update_out_of_sequence(
    async_docker_client: aiodocker.Docker, mock_service: str, docker_swarm: None
):
    # NOTE: checks that the docker engine replies with
    # `rpc error: code = Unknown desc = update out of sequence`
    # the error is captured and raised as `docker_api._RetryError`
    with pytest.raises(TryAgain):
        # starting concurrent updates will trigger the error
        await asyncio.gather(
            *[
                _update_service_spec(
                    service_name=mock_service,
                    update_in_service_spec={},
                    stop_delay=3,
                )
                for _ in range(10)
            ]
        )


@pytest.fixture
async def target_node_id(async_docker_client: aiodocker.Docker) -> str:
    # get a node's ID
    docker_nodes = await async_docker_client.nodes.list()
    return docker_nodes[0]["ID"]


async def test_constrain_service_to_node(
    async_docker_client: aiodocker.Docker,
    mock_service: str,
    target_node_id: str,
    docker_swarm: None,
):
    await docker_api.constrain_service_to_node(
        mock_service, docker_node_id=target_node_id
    )

    # check constraint was added
    service_inspect = await async_docker_client.services.inspect(mock_service)
    constraints: list[str] = service_inspect["Spec"]["TaskTemplate"]["Placement"][
        "Constraints"
    ]
    assert len(constraints) == 1, constraints
    node_id_constraint = constraints[0]
    label, value = node_id_constraint.split("==")
    assert label.strip() == "node.id"
    assert value.strip() == target_node_id


@pytest.fixture
async def named_volumes(
    async_docker_client: aiodocker.Docker, faker: Faker
) -> AsyncIterator[list[str]]:
    named_volumes: list[DockerVolume] = []
    volume_names: list[str] = []
    for _ in range(10):
        named_volume: DockerVolume = await async_docker_client.volumes.create(
            {"Name": f"named-volume-{faker.uuid4()}"}
        )
        volume_names.append(named_volume.name)
        named_volumes.append(named_volume)

    yield volume_names

    # remove volume if still present
    for named_volume in named_volumes:
        with contextlib.suppress(aiodocker.DockerError):
            await named_volume.delete()


async def is_volume_present(
    async_docker_client: aiodocker.Docker, volume_name: str
) -> bool:
    list_of_volumes = await async_docker_client.volumes.list()
    for volume in list_of_volumes.get("Volumes", []):
        if volume["Name"] == volume_name:
            return True
    return False


async def test_remove_volume_from_node_ok(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
    named_volumes: list[str],
    target_node_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
):
    for named_volume in named_volumes:
        assert await is_volume_present(async_docker_client, named_volume) is True

    volume_removal_result = await docker_api.remove_volumes_from_node(
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        volume_names=named_volumes,
        docker_node_id=target_node_id,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
    )
    assert volume_removal_result is True

    for named_volume in named_volumes:
        assert await is_volume_present(async_docker_client, named_volume) is False


async def test_remove_volume_from_node_no_volume_found(
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
    named_volumes: list[str],
    target_node_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
):
    missing_volume_name = "nope-i-am-fake-and-do-not-exist"
    assert await is_volume_present(async_docker_client, missing_volume_name) is False

    # put the missing one in the middle of the sequence
    volumes_to_remove = named_volumes[:1] + [missing_volume_name] + named_volumes[1:]

    volume_removal_result = await docker_api.remove_volumes_from_node(
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        volume_names=volumes_to_remove,
        docker_node_id=target_node_id,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        volume_removal_attempts=2,
        sleep_between_attempts_s=1,
    )
    assert volume_removal_result is True
    assert await is_volume_present(async_docker_client, missing_volume_name) is False
    for named_volume in named_volumes:
        assert await is_volume_present(async_docker_client, named_volume) is False


@pytest.fixture
def volume_removal_services_names(faker: Faker) -> set[str]:
    return {f"{DYNAMIC_VOLUME_REMOVER_PREFIX}_{faker.uuid4()}" for _ in range(10)}


@pytest.fixture(params=[0, 2])
def service_timeout_s(request: pytest.FixtureRequest) -> int:
    return request.param  # type: ignore


@pytest.fixture
async def ensure_fake_volume_removal_services(
    async_docker_client: aiodocker.Docker,
    docker_version: DockerVersion,
    target_node_id: str,
    user_id: UserID,
    project_id: ProjectID,
    node_uuid: NodeID,
    volume_removal_services_names: list[str],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    service_timeout_s: int,
    docker_swarm: None,
) -> AsyncIterator[None]:
    started_services_ids: list[str] = []

    for service_name in volume_removal_services_names:
        service_spec = spec_volume_removal_service(
            dynamic_sidecar_settings=dynamic_sidecar_settings,
            docker_node_id=target_node_id,
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            volume_names=[],
            docker_version=docker_version,
            volume_removal_attempts=0,
            sleep_between_attempts_s=0,
            service_timeout_s=service_timeout_s,
        )

        # replace values
        service_spec.Name = service_name
        # use very long sleep command
        service_spec.TaskTemplate.ContainerSpec.Command = ["sh", "-c", "sleep 3600"]

        started_service = await async_docker_client.services.create(
            **jsonable_encoder(service_spec, by_alias=True, exclude_unset=True)
        )
        started_services_ids.append(started_service["ID"])

    yield None

    for service_id in started_services_ids:
        try:
            await async_docker_client.services.delete(service_id)
        except aiodocker.exceptions.DockerError as e:
            assert e.message == f"service {service_id} not found"


async def _get_pending_services(async_docker_client: aiodocker.Docker) -> list[str]:
    service_filters = {"name": [f"{DYNAMIC_VOLUME_REMOVER_PREFIX}"]}
    return [
        x["Spec"]["Name"]
        for x in await async_docker_client.services.list(filters=service_filters)
    ]


async def test_get_volume_removal_services(
    ensure_fake_volume_removal_services: None,
    async_docker_client: aiodocker.Docker,
    volume_removal_services_names: set[str],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    service_timeout_s: int,
):
    # services will be detected as timed out after 1 second
    sleep_for = 1.01
    await asyncio.sleep(sleep_for)

    pending_service_names = await _get_pending_services(async_docker_client)
    assert len(pending_service_names) == len(volume_removal_services_names)

    # check services are present before removing timed out services
    for service_name in pending_service_names:
        assert service_name in volume_removal_services_names

    await docker_api.remove_pending_volume_removal_services(dynamic_sidecar_settings)

    # check that timed out services have been removed
    pending_service_names = await _get_pending_services(async_docker_client)
    services_have_timed_out = sleep_for > service_timeout_s
    if services_have_timed_out:
        assert len(pending_service_names) == 0
    else:
        assert len(pending_service_names) == len(volume_removal_services_names)
        for service_name in pending_service_names:
            assert service_name in volume_removal_services_names
