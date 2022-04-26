# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from typing import Any, AsyncIterable, AsyncIterator, Dict, List
from uuid import UUID, uuid4

import aiodocker
import pytest
from _pytest.monkeypatch import MonkeyPatch
from aiodocker.utils import clean_filters
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from simcore_service_director_v2.core.settings import DynamicSidecarSettings
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.models.schemas.dynamic_services import (
    SchedulerData,
    ServiceState,
    ServiceType,
)
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    DockerContainerInspect,
    SimcoreServiceLabels,
)
from simcore_service_director_v2.modules.dynamic_sidecar import docker_api
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api import (
    update_scheduler_data_label,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarError,
    GenericDockerError,
)

MAX_INT64 = 9223372036854775807

# FIXTURES


@pytest.fixture
async def async_docker_client(
    docker_swarm: None,
) -> AsyncIterator[aiodocker.docker.Docker]:
    async with aiodocker.Docker() as client:
        yield client


@pytest.fixture
def dynamic_sidecar_settings(
    monkeypatch: MonkeyPatch, docker_swarm: None
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
    monkeypatch.setenv("R_CLONE_STORAGE_ENDPOINT", "storage_endpoint")
    return DynamicSidecarSettings.create_from_envs()


@pytest.fixture
def network_config(simcore_services_network_name: str) -> Dict[str, Any]:
    return {
        "Name": simcore_services_network_name,
        "Driver": "overlay",
        "Labels": {"uuid": f"{uuid4()}"},
    }


@pytest.fixture
async def ensure_swarm_network(
    network_config: Dict[str, Any],
    async_docker_client: aiodocker.docker.Docker,
    docker_swarm: None,
) -> AsyncIterator[None]:
    network_id = None
    try:
        network_id = await docker_api.create_network(network_config)
        yield
    finally:
        if network_id is not None:
            docker_network = await async_docker_client.networks.get(network_id)
            assert await docker_network.delete() is True


@pytest.fixture
async def cleanup_swarm_network(
    simcore_services_network_name: str,
    async_docker_client: aiodocker.docker.Docker,
    docker_swarm: None,
) -> AsyncIterator[None]:
    yield
    docker_network = await async_docker_client.networks.get(
        simcore_services_network_name
    )
    assert await docker_network.delete() is True


@pytest.fixture
def missing_network_name() -> str:
    return "this_network_is_missing"


@pytest.fixture
def test_service_name() -> str:
    return "test_service_name"


@pytest.fixture
def service_spec(test_service_name: str) -> Dict[str, Any]:
    # "joseluisq/static-web-server" is ~2MB docker image
    return {
        "name": test_service_name,
        "task_template": {"ContainerSpec": {"Image": "joseluisq/static-web-server"}},
        "labels": {"foo": "bar"},
    }


@pytest.fixture
async def cleanup_test_service_name(
    test_service_name: str,
    async_docker_client: aiodocker.docker.Docker,
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
) -> Dict[str, Any]:
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
    async_docker_client: aiodocker.docker.Docker,
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
) -> List[Dict[str, Any]]:
    return [
        {
            "name": f"{DYNAMIC_PROXY_SERVICE_PREFIX}_fake_proxy",
            "task_template": {
                "ContainerSpec": {"Image": "joseluisq/static-web-server"}
            },
            "labels": {
                "swarm_stack_name": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}",
                "type": f"{ServiceType.DEPENDENCY.value}",
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
                "type": f"{ServiceType.MAIN.value}",
                "uuid": f"{node_uuid}",
                "user_id": f"{user_id}",
                "study_id": f"{project_id}",
            },
        },
    ]


@pytest.fixture
async def cleanup_dynamic_sidecar_stack(
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    async_docker_client: aiodocker.docker.Docker,
) -> AsyncIterator[None]:
    yield
    for dynamic_sidecar_spec in dynamic_sidecar_stack_specs:
        assert (
            await async_docker_client.services.delete(dynamic_sidecar_spec["name"])
            is True
        )


@pytest.fixture
async def project_id_labeled_network(
    async_docker_client: aiodocker.docker.Docker, project_id: ProjectID
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
    async_docker_client: aiodocker.docker.Docker, docker_swarm: None
) -> AsyncIterator[List[str]]:
    network_names = [f"test_network_name__{k}" for k in range(5)]

    yield network_names

    for network_name in network_names:
        docker_network = await async_docker_client.networks.get(network_name)
        assert await docker_network.delete() is True


@pytest.fixture
async def existing_network(
    async_docker_client: aiodocker.docker.Docker, project_id: ProjectID
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
def labels_example(request) -> SimcoreServiceLabels:
    return request.param


@pytest.fixture
def mock_scheduler_data(
    labels_example: SimcoreServiceLabels,
    scheduler_data: SchedulerData,
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
async def docker() -> AsyncIterable[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client


@pytest.fixture
async def mock_service(
    docker: aiodocker.Docker, service_name: str
) -> AsyncIterable[str]:
    service_data = await docker.services.create(
        {"ContainerSpec": {"Image": "joseluisq/static-web-server:1.16.0-alpine"}},
        name=service_name,
    )

    yield service_name

    await docker.services.delete(service_data["ID"])


# UTILS


def _assert_service(
    service_spec: Dict[str, Any], service_inspect: Dict[str, Any]
) -> None:
    assert service_inspect["Spec"]["Labels"] == service_spec["labels"]
    assert service_inspect["Spec"]["Name"] == service_spec["name"]
    assert (
        service_inspect["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"]
        == service_spec["task_template"]["ContainerSpec"]["Image"]
    )


async def _count_services_in_stack(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    async_docker_client: aiodocker.docker.Docker,
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


def _inject_impossible_resources(dynamic_sidecar_service_spec: Dict[str, Any]) -> None:
    dynamic_sidecar_service_spec["task_template"]["Resources"] = {
        "Reservations": {"NanoCPUs": MAX_INT64, "MemoryBytes": MAX_INT64}
    }


# TESTS


def test_new_docker_swarm(docker_swarm: None) -> None:
    pass


@pytest.mark.parametrize(
    "simcore_services_network_name",
    ("n", "network", "with_underscore", "with-dash", "with-dash_with_underscore"),
)
def test_valid_network_names(
    simcore_services_network_name: str, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:MOCKED")
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", simcore_services_network_name)
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    dynamic_sidecar_settings = DynamicSidecarSettings.create_from_envs()
    assert dynamic_sidecar_settings


async def test_failed_docker_client_request(
    missing_network_name: str, docker_swarm: None
) -> None:
    with pytest.raises(GenericDockerError) as execinfo:
        async with docker_api.docker_client() as client:
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
) -> None:
    swarm_network = await docker_api.get_swarm_network(dynamic_sidecar_settings)
    assert swarm_network["Name"] == simcore_services_network_name


async def test_get_swarm_network_missing_network(
    dynamic_sidecar_settings: DynamicSidecarSettings, docker_swarm: None
) -> None:
    with pytest.raises(DynamicSidecarError) as excinfo:
        await docker_api.get_swarm_network(dynamic_sidecar_settings)
    assert str(excinfo.value) == (
        "Swarm network name (searching for '*test_network_name*') is not configured."
        "Found following networks: []"
    )


async def test_recreate_network_multiple_times(
    network_config: Dict[str, Any],
    cleanup_swarm_network: None,
    docker_swarm: None,
) -> None:
    network_ids = [await docker_api.create_network(network_config) for _ in range(10)]
    network_ids_set = set(network_ids)
    assert len(network_ids_set) == 1
    network_id = network_ids_set.pop()
    assert type(network_id) == str


async def test_create_service(
    service_spec: Dict[str, Any],
    cleanup_test_service_name: None,
    docker_swarm: None,
) -> None:
    service_id = await docker_api.create_service_and_get_id(service_spec)
    assert service_id


async def test_inspect_service(
    service_spec: Dict[str, Any],
    cleanup_test_service_name: None,
    docker_swarm: None,
) -> None:
    service_id = await docker_api.create_service_and_get_id(service_spec)
    assert service_id

    service_inspect = await docker_api.inspect_service(service_id)

    _assert_service(service_spec, service_inspect)


async def test_services_to_observe_exist(
    dynamic_sidecar_service_name: str,
    dynamic_sidecar_service_spec: Dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
) -> None:
    service_id = await docker_api.create_service_and_get_id(
        dynamic_sidecar_service_spec
    )
    assert service_id

    dynamic_services = await docker_api.get_dynamic_sidecars_to_observe(
        dynamic_sidecar_settings
    )
    assert len(dynamic_services) == 1

    for entry in dynamic_services:
        assert entry.service_name == dynamic_sidecar_service_name


async def test_dynamic_sidecar_in_running_state_and_node_id_is_recovered(
    dynamic_sidecar_service_spec: Dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
) -> None:
    service_id = await docker_api.create_service_and_get_id(
        dynamic_sidecar_service_spec
    )
    assert service_id

    node_id = await docker_api.get_node_id_from_task_for_service(
        service_id, dynamic_sidecar_settings
    )
    assert node_id

    # after the node_id is recovered the service
    # will be in a running state
    dynamic_sidecar_state = await docker_api.get_dynamic_sidecar_state(service_id)
    assert dynamic_sidecar_state == (ServiceState.RUNNING, "")


async def test_dynamic_sidecar_get_dynamic_sidecar_sate_fail_to_schedule(
    dynamic_sidecar_service_spec: Dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
) -> None:
    _inject_impossible_resources(dynamic_sidecar_service_spec)
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


async def test_is_dynamic_sidecar_missing(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
) -> None:

    services_are_missing = await docker_api.is_dynamic_sidecar_missing(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing == True

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await docker_api.is_dynamic_sidecar_missing(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing == False


async def test_are_all_services_present(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    services_are_missing = await docker_api.are_all_services_present(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing == False

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await docker_api.are_all_services_present(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing == True


async def test_remove_dynamic_sidecar_stack(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    docker_swarm: None,
    async_docker_client: aiodocker.docker.Docker,
):
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
    network_config: Dict[str, Any],
    simcore_services_network_name: str,
    docker_swarm: None,
) -> None:
    network_ids = [await docker_api.create_network(network_config) for _ in range(10)]
    assert len(set(network_ids)) == 1

    delete_result = await docker_api.remove_dynamic_sidecar_network(
        simcore_services_network_name
    )
    assert delete_result is True


async def test_remove_dynamic_sidecar_network_fails(
    simcore_services_network_name: str, docker_swarm: None
) -> None:
    delete_result = await docker_api.remove_dynamic_sidecar_network(
        simcore_services_network_name
    )
    assert delete_result is False


async def test_list_dynamic_sidecar_services(
    node_uuid: UUID,
    user_id: UserID,
    project_id: ProjectID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services = await docker_api.list_dynamic_sidecar_services(
        dynamic_sidecar_settings, user_id=user_id, project_id=project_id
    )
    assert len(services) == 1


async def test_is_dynamic_service_running(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
) -> None:
    assert (
        await docker_api.is_dynamic_service_running(node_uuid, dynamic_sidecar_settings)
        is False
    )

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    assert (
        await docker_api.is_dynamic_service_running(node_uuid, dynamic_sidecar_settings)
        is True
    )


async def test_get_projects_networks_containers(
    async_docker_client: aiodocker.docker.Docker,
    project_id_labeled_network: str,
    project_id: ProjectID,
    docker_swarm: None,
) -> None:
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
    test_networks: List[str], existing_network: str, project_id: ProjectID
):
    # test with duplicate networks and existing networks
    networks_to_test = test_networks + test_networks + [existing_network]
    network_ids = await docker_api.get_or_create_networks_ids(
        networks=networks_to_test,
        project_id=project_id,
    )
    assert set(networks_to_test) == set(network_ids.keys())


async def test_update_scheduler_data_label(
    docker: aiodocker.Docker,
    mock_service: str,
    mock_scheduler_data: SchedulerData,
    docker_swarm: None,
) -> None:
    await update_scheduler_data_label(mock_scheduler_data)

    # fetch stored data in labels
    service_inspect = await docker.services.inspect(mock_service)
    labels = service_inspect["Spec"]["Labels"]
    scheduler_data = SchedulerData.parse_raw(
        labels[DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL]
    )
    assert scheduler_data == mock_scheduler_data
