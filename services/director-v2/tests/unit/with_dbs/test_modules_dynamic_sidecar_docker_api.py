# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=protected-access

import asyncio
import datetime
import logging
import sys
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import aiodocker
import pytest
from aiodocker.utils import clean_filters
from faker import Faker
from models_library.docker import to_simcore_runtime_docker_label_key
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_enums import ServiceState
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict
from simcore_service_director_v2.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
)
from simcore_service_director_v2.core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from simcore_service_director_v2.core.dynamic_services_settings.sidecar import (
    DynamicSidecarSettings,
)
from simcore_service_director_v2.models.dynamic_services_scheduler import (
    DockerContainerInspect,
    SchedulerData,
    SimcoreServiceLabels,
)
from simcore_service_director_v2.modules.dynamic_sidecar import docker_api
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api._core import (
    _update_service_spec,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api._utils import (
    docker_client,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarError,
    GenericDockerError,
)
from tenacity import TryAgain
from tenacity.asyncio import AsyncRetrying
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
def dynamic_services_scheduler_settings(
    monkeypatch: pytest.MonkeyPatch, mock_env: EnvVarsDict
) -> DynamicServicesSchedulerSettings:
    monkeypatch.setenv("SIMCORE_SERVICES_NETWORK_NAME", "test_network_name")
    monkeypatch.setenv("SWARM_STACK_NAME", "test_swarm_name")
    return DynamicServicesSchedulerSettings.create_from_envs()


@pytest.fixture
def dynamic_sidecar_settings(
    monkeypatch: pytest.MonkeyPatch, mock_env: EnvVarsDict, faker: Faker
) -> DynamicSidecarSettings:
    monkeypatch.setenv("DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:MOCKED")
    monkeypatch.setenv("DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("TRAEFIK_SIMCORE_ZONE", "test_traefik_zone")

    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())
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
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    scheduler_data_from_http_request: SchedulerData,
) -> dict[str, Any]:
    # "joseluisq/static-web-server" is ~2MB docker image
    scheduler_data_from_http_request.service_name = dynamic_sidecar_service_name

    return {
        "name": dynamic_sidecar_service_name,
        "task_template": {"ContainerSpec": {"Image": "joseluisq/static-web-server"}},
        "labels": {
            "traefik.docker.network": "",
            "io.simcore.zone": "",
            f"{to_simcore_runtime_docker_label_key('project_id')}": f"{uuid4()}",
            f"{to_simcore_runtime_docker_label_key('user_id')}": "123",
            f"{to_simcore_runtime_docker_label_key('node_id')}": f"{uuid4()}",
            f"{to_simcore_runtime_docker_label_key('swarm_stack_name')}": f"{dynamic_services_scheduler_settings.SWARM_STACK_NAME}",
            f"{to_simcore_runtime_docker_label_key('service_port')}": "80",
            f"{to_simcore_runtime_docker_label_key('service_key')}": "simcore/services/dynamic/3dviewer",
            f"{to_simcore_runtime_docker_label_key('service_version')}": "2.4.5",
            DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL: scheduler_data_from_http_request.model_dump_json(),
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
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
) -> list[dict[str, Any]]:
    return [
        {
            "name": f"{DYNAMIC_PROXY_SERVICE_PREFIX}_fake_proxy",
            "task_template": {
                "ContainerSpec": {"Image": "joseluisq/static-web-server"}
            },
            "labels": {
                f"{to_simcore_runtime_docker_label_key('project_id')}": f"{project_id}",
                f"{to_simcore_runtime_docker_label_key('user_id')}": f"{user_id}",
                f"{to_simcore_runtime_docker_label_key('node_id')}": f"{node_uuid}",
                f"{to_simcore_runtime_docker_label_key('swarm_stack_name')}": f"{dynamic_services_scheduler_settings.SWARM_STACK_NAME}",
                f"{to_simcore_runtime_docker_label_key('service_port')}": "80",
                f"{to_simcore_runtime_docker_label_key('service_key')}": "simcore/services/dynamic/3dviewer",
                f"{to_simcore_runtime_docker_label_key('service_version')}": "2.4.5",
            },
        },
        {
            "name": f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_fake_sidecar",
            "task_template": {
                "ContainerSpec": {"Image": "joseluisq/static-web-server"}
            },
            "labels": {
                f"{to_simcore_runtime_docker_label_key('project_id')}": f"{project_id}",
                f"{to_simcore_runtime_docker_label_key('user_id')}": f"{user_id}",
                f"{to_simcore_runtime_docker_label_key('node_id')}": f"{node_uuid}",
                f"{to_simcore_runtime_docker_label_key('swarm_stack_name')}": f"{dynamic_services_scheduler_settings.SWARM_STACK_NAME}",
                f"{to_simcore_runtime_docker_label_key('service_port')}": "80",
                f"{to_simcore_runtime_docker_label_key('service_key')}": "simcore/services/dynamic/3dviewer",
                f"{to_simcore_runtime_docker_label_key('service_version')}": "2.4.5",
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
        SimcoreServiceLabels.model_validate(example)
        for example in SimcoreServiceLabels.model_config["json_schema_extra"][
            "examples"
        ]
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
    ["n", "network", "with_underscore", "with-dash", "with-dash_with_underscore"],
)
def test_settings__valid_network_names(
    simcore_services_network_name: str,
    monkeypatch: pytest.MonkeyPatch,
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
) -> None:
    items = dynamic_services_scheduler_settings.model_dump()
    items["SIMCORE_SERVICES_NETWORK_NAME"] = simcore_services_network_name

    # validate network names
    DynamicServicesSchedulerSettings.model_validate(items)


async def test_failed_docker_client_request(docker_swarm: None):
    missing_network_name = "this_network_cannot_be_found"

    with pytest.raises(
        GenericDockerError,
        match=f"Unexpected error using docker client: network {missing_network_name} not found",
    ):
        async with docker_client() as client:
            await client.networks.get(missing_network_name)


async def test_get_swarm_network_ok(
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    simcore_services_network_name: str,
    ensure_swarm_network: None,
    docker_swarm: None,
):
    swarm_network = await docker_api.get_swarm_network(
        dynamic_services_scheduler_settings.SIMCORE_SERVICES_NETWORK_NAME
    )
    assert swarm_network["Name"] == simcore_services_network_name


async def test_get_swarm_network_missing_network(
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    docker_swarm: None,
):
    with pytest.raises(
        DynamicSidecarError,
        match=r"Unexpected dynamic sidecar error: "
        r"Swarm network name \(searching for \'\*test_network_name\*\'\) is not configured."
        r"Found following networks: \[\]",
    ):
        await docker_api.get_swarm_network(
            dynamic_services_scheduler_settings.SIMCORE_SERVICES_NETWORK_NAME
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
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
):
    service_id = await docker_api.create_service_and_get_id(
        dynamic_sidecar_service_spec
    )
    assert service_id

    dynamic_services = await docker_api.get_dynamic_sidecars_to_observe(
        dynamic_services_scheduler_settings.SWARM_STACK_NAME
    )
    assert len(dynamic_services) == 1

    assert dynamic_services[0].service_name == dynamic_sidecar_service_name


async def test_dynamic_sidecar_in_running_state_and_node_id_is_recovered(
    dynamic_sidecar_service_spec: dict[str, Any],
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
):
    service_id = await docker_api.create_service_and_get_id(
        dynamic_sidecar_service_spec
    )
    assert service_id

    node_id = await docker_api.get_dynamic_sidecar_placement(
        service_id, dynamic_services_scheduler_settings
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
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    services_are_missing = await docker_api.is_dynamic_sidecar_stack_missing(
        node_uuid, dynamic_services_scheduler_settings.SWARM_STACK_NAME
    )
    assert services_are_missing is True

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await docker_api.is_dynamic_sidecar_stack_missing(
        node_uuid, dynamic_services_scheduler_settings.SWARM_STACK_NAME
    )
    assert services_are_missing is False


async def test_are_sidecar_and_proxy_services_present(
    node_uuid: UUID,
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    services_are_missing = await docker_api.are_sidecar_and_proxy_services_present(
        node_uuid, dynamic_services_scheduler_settings.SWARM_STACK_NAME
    )
    assert services_are_missing is False

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await docker_api.create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await docker_api.are_sidecar_and_proxy_services_present(
        node_uuid, dynamic_services_scheduler_settings.SWARM_STACK_NAME
    )
    assert services_are_missing is True


async def test_remove_dynamic_sidecar_stack(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    docker_swarm: None,
    async_docker_client: aiodocker.Docker,
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
):
    async def _count_services_in_stack(
        node_uuid: UUID,
        dynamic_sidecar_settings: DynamicSidecarSettings,
        async_docker_client: aiodocker.Docker,
    ) -> int:
        services = await async_docker_client.services.list(
            filters={
                "label": [
                    f"{to_simcore_runtime_docker_label_key('swarm_stack_name')}={dynamic_services_scheduler_settings.SWARM_STACK_NAME}",
                    f"{to_simcore_runtime_docker_label_key('node_id')}={node_uuid}",
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

    await docker_api.remove_dynamic_sidecar_stack(
        node_uuid, dynamic_services_scheduler_settings.SWARM_STACK_NAME
    )

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
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    dynamic_sidecar_stack_specs: list[dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
):
    assert (
        await docker_api.is_sidecar_running(
            node_uuid, dynamic_services_scheduler_settings.SWARM_STACK_NAME
        )
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
                node_uuid, dynamic_services_scheduler_settings.SWARM_STACK_NAME
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
    scheduler_data = SchedulerData.model_validate_json(
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
