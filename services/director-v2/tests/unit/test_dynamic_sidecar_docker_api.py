# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from asyncio import BaseEventLoop
from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest
from models_library.projects import ProjectID
from settings_library.docker_registry import RegistrySettings
from simcore_service_director_v2.core.settings import DynamicSidecarSettings
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_PROXY_SERVICE_PREFIX,
    DYNAMIC_SIDECAR_SERVICE_PREFIX,
    UserID,
)
from simcore_service_director_v2.models.schemas.dynamic_services import (
    ServiceLabelsStoredData,
    ServiceState,
    ServiceType,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_api import (
    are_all_services_present,
    are_services_missing,
    create_network,
    create_service_and_get_id,
    docker_client,
    get_dynamic_sidecar_state,
    get_dynamic_sidecars_to_monitor,
    get_node_id_from_task_for_service,
    get_swarm_network,
    inspect_service,
    is_dynamic_service_running,
    list_dynamic_sidecar_services,
    remove_dynamic_sidecar_network,
    remove_dynamic_sidecar_stack,
)
from simcore_service_director_v2.modules.dynamic_sidecar.errors import (
    DynamicSidecarError,
    GenericDockerError,
)

pytestmark = pytest.mark.asyncio

# FIXTURES


@pytest.fixture
def dynamic_sidecar_settings(monkeypatch) -> DynamicSidecarSettings:
    monkeypatch.setenv(
        "DYNAMIC_SIDECAR_IMAGE", "local/dynamic-sidecar:TEST_MOCKED_TAG_NOT_PRESENT"
    )
    return DynamicSidecarSettings(REGISTRY=RegistrySettings())


@pytest.fixture
def network_config(simcore_services_network_name: str) -> Dict[str, Any]:
    return {
        "Name": simcore_services_network_name,
        "Driver": "overlay",
        "Labels": {"uuid": f"{uuid4()}"},
    }


@pytest.fixture
async def ensure_swarm_network(
    loop: BaseEventLoop, network_config: Dict[str, Any]
) -> None:
    network_id = None
    async with docker_client() as client:
        try:
            network_id = await create_network(network_config)
            yield
        finally:
            if network_id is not None:
                docker_network = await client.networks.get(network_id)
                assert await docker_network.delete() is True


@pytest.fixture
async def cleanup_swarm_network(
    loop: BaseEventLoop, simcore_services_network_name: str
) -> None:
    yield
    async with docker_client() as client:
        docker_network = await client.networks.get(simcore_services_network_name)
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
    loop: BaseEventLoop, test_service_name: str
) -> None:
    yield
    async with docker_client() as client:
        assert await client.services.delete(test_service_name) is True


@pytest.fixture
def dynamic_sidecar_service_name() -> str:
    return f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_some-dynamic-fake-sidecar"


@pytest.fixture
def dynamic_sidecar_service_spec(
    dynamic_sidecar_service_name: str, dynamic_sidecar_settings: DynamicSidecarSettings
) -> Dict[str, Any]:
    # "joseluisq/static-web-server" is ~2MB docker image
    sample = ServiceLabelsStoredData.Config.schema_extra["example"]

    return {
        "name": dynamic_sidecar_service_name,
        "task_template": {"ContainerSpec": {"Image": "joseluisq/static-web-server"}},
        "labels": {
            "swarm_stack_name": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}",
            "uuid": f"{uuid4()}",
            "service_key": "simcore/services/dynamic/3dviewer",
            "service_tag": "2.4.5",
            "paths_mapping": sample["paths_mapping"].json(),
            "compose_spec": json.dumps(sample["compose_spec"]),
            "container_http_entry": sample["container_http_entry"],
            "traefik.docker.network": "",
            "io.simcore.zone": "",
            "service_port": "80",
            "study_id": f"{uuid4()}",
            "user_id": "123",
        },
    }


@pytest.fixture
async def cleanup_test_dynamic_sidecar_service(
    loop: BaseEventLoop, dynamic_sidecar_service_name: str
) -> None:
    yield
    async with docker_client() as client:
        assert await client.services.delete(dynamic_sidecar_service_name) is True


@pytest.fixture
def node_uuid() -> UUID:
    return uuid4()


@pytest.fixture
def user_id() -> UserID:
    return 123


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


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
    loop: BaseEventLoop, dynamic_sidecar_stack_specs: List[Dict[str, Any]]
) -> None:
    yield
    async with docker_client() as client:
        for dynamic_sidecar_spec in dynamic_sidecar_stack_specs:
            assert await client.services.delete(dynamic_sidecar_spec["name"]) is True


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
    node_uuid: UUID, dynamic_sidecar_settings: DynamicSidecarSettings
) -> int:
    async with docker_client() as client:
        services = await client.services.list(
            filters={
                "label": [
                    f"swarm_stack_name={dynamic_sidecar_settings.SWARM_STACK_NAME}",
                    f"uuid={node_uuid}",
                ]
            }
        )
        return len(services)


# TESTS


async def test_failed_docker_client_request(
    missing_network_name: str, docker_swarm: None
) -> None:
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
) -> None:
    swarm_network = await get_swarm_network(dynamic_sidecar_settings)
    assert swarm_network["Name"] == simcore_services_network_name


async def test_get_swarm_network_missing_network(
    dynamic_sidecar_settings: DynamicSidecarSettings, docker_swarm: None
) -> None:
    with pytest.raises(DynamicSidecarError) as excinfo:
        await get_swarm_network(dynamic_sidecar_settings)
    assert (
        str(excinfo.value)
        == "Swarm network name is not configured, found following networks: []"
    )


async def test_recreate_network_multiple_times(
    network_config: Dict[str, Any],
    cleanup_swarm_network: None,
    docker_swarm: None,
) -> None:
    network_ids = [await create_network(network_config) for _ in range(10)]
    assert len(set(network_ids)) == 1


async def test_create_service(
    service_spec: Dict[str, Any],
    cleanup_test_service_name: None,
    docker_swarm: None,
) -> None:
    service_id = await create_service_and_get_id(service_spec)
    assert service_id


async def test_inspect_service(
    service_spec: Dict[str, Any],
    cleanup_test_service_name: None,
    docker_swarm: None,
) -> None:
    service_id = await create_service_and_get_id(service_spec)
    assert service_id

    service_inspect = await inspect_service(service_id)

    _assert_service(service_spec, service_inspect)


async def test_services_to_monitor_exist(
    dynamic_sidecar_service_name: str,
    dynamic_sidecar_service_spec: Dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
) -> None:
    service_id = await create_service_and_get_id(dynamic_sidecar_service_spec)
    assert service_id

    dynamic_services = await get_dynamic_sidecars_to_monitor(dynamic_sidecar_settings)
    assert len(dynamic_services) == 1

    for entry in dynamic_services:
        assert entry.service_name == dynamic_sidecar_service_name


async def test_dynamic_sidecar_in_running_state_and_node_id_is_recovered(
    dynamic_sidecar_service_spec: Dict[str, Any],
    dynamic_sidecar_settings: DynamicSidecarSettings,
    cleanup_test_dynamic_sidecar_service: None,
    docker_swarm: None,
) -> None:
    service_id = await create_service_and_get_id(dynamic_sidecar_service_spec)
    assert service_id

    node_id = await get_node_id_from_task_for_service(
        service_id, dynamic_sidecar_settings
    )
    assert node_id

    # after the node_id is recovered the service
    # will be in a running state
    dynamic_sidecar_state = await get_dynamic_sidecar_state(
        service_id, dynamic_sidecar_settings
    )
    assert dynamic_sidecar_state == (ServiceState.RUNNING, "")


async def test_are_services_missing(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    cleanup_dynamic_sidecar_stack: None,
    docker_swarm: None,
) -> None:

    services_are_missing = await are_services_missing(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing == True

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await are_services_missing(
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
    services_are_missing = await are_all_services_present(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing == False

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services_are_missing = await are_all_services_present(
        node_uuid, dynamic_sidecar_settings
    )
    assert services_are_missing == True


async def test_remove_dynamic_sidecar_stack(
    node_uuid: UUID,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_stack_specs: List[Dict[str, Any]],
    docker_swarm: None,
):
    assert await _count_services_in_stack(node_uuid, dynamic_sidecar_settings) == 0

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    assert await _count_services_in_stack(node_uuid, dynamic_sidecar_settings) == 2

    await remove_dynamic_sidecar_stack(node_uuid, dynamic_sidecar_settings)

    assert await _count_services_in_stack(node_uuid, dynamic_sidecar_settings) == 0


async def test_remove_dynamic_sidecar_network(
    network_config: Dict[str, Any],
    simcore_services_network_name: str,
    docker_swarm: None,
) -> None:
    network_ids = [await create_network(network_config) for _ in range(10)]
    assert len(set(network_ids)) == 1

    delete_result = await remove_dynamic_sidecar_network(simcore_services_network_name)
    assert delete_result is True


async def test_remove_dynamic_sidecar_network_fails(
    simcore_services_network_name: str, docker_swarm: None
) -> None:
    delete_result = await remove_dynamic_sidecar_network(simcore_services_network_name)
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
        service_id = await create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    services = await list_dynamic_sidecar_services(
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
        await is_dynamic_service_running(node_uuid, dynamic_sidecar_settings) is False
    )

    # start 2 fake services to emulate the dynamic-sidecar stack
    for dynamic_sidecar_stack in dynamic_sidecar_stack_specs:
        service_id = await create_service_and_get_id(dynamic_sidecar_stack)
        assert service_id

    assert await is_dynamic_service_running(node_uuid, dynamic_sidecar_settings) is True
