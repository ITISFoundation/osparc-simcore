# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from collections.abc import AsyncIterable, AsyncIterator

import aiodocker
import pytest
import yaml
from aiodocker.containers import DockerContainer
from faker import Faker
from models_library.generated_models.docker_rest_api import ContainerState
from models_library.services import ServiceRunID
from pydantic import PositiveInt
from simcore_service_dynamic_sidecar.core.docker_utils import (
    _get_containers_inspect_from_names,
    get_container_states,
    get_containers_count_from_names,
    get_docker_service_images,
    get_volume_by_label,
)
from simcore_service_dynamic_sidecar.core.errors import VolumeNotFoundError


@pytest.fixture
def volume_name() -> str:
    return "test_source_name"


@pytest.fixture
def service_run_id() -> ServiceRunID:
    return ServiceRunID.get_resource_tracking_run_id_for_dynamic()


@pytest.fixture
async def volume_with_label(
    volume_name: str, service_run_id: ServiceRunID
) -> AsyncIterable[None]:
    async with aiodocker.Docker() as docker_client:
        volume = await docker_client.volumes.create(
            {
                "Name": "test_volume_name_1",
                "Labels": {"source": volume_name, "run_id": service_run_id},
            }
        )

        yield

        await volume.delete()


@pytest.fixture(params=[0, 1, 2, 3])
def container_count(request: pytest.FixtureRequest) -> PositiveInt:
    return request.param


@pytest.fixture
def container_names(container_count: PositiveInt) -> list[str]:
    return [f"container_test_{i}" for i in range(container_count)]


@pytest.fixture
async def started_services(container_names: list[str]) -> AsyncIterator[None]:
    async with aiodocker.Docker() as docker_client:
        started_containers = []
        for container_name in container_names:
            container = await docker_client.containers.run(
                config={"Image": "alpine:latest", "Cmd": ["sh", "-c", "sleep 10000"]},
                name=container_name,
            )
            started_containers.append(container)

        yield

        for container in started_containers:
            await container.delete(force=True)


async def test_volume_with_label(
    volume_with_label: None, volume_name: str, service_run_id: ServiceRunID
) -> None:
    assert await get_volume_by_label(volume_name, service_run_id)


async def test_volume_label_missing(service_run_id: ServiceRunID) -> None:
    with pytest.raises(VolumeNotFoundError) as exc_info:
        await get_volume_by_label("not_exist", service_run_id)

    error_msg = f"{exc_info.value}"
    assert service_run_id in error_msg
    assert "not_exist" in error_msg


async def test__get_containers_inspect_from_names(
    started_services: None, container_names: list[str], faker: Faker
):
    MISSING_CONTAINER_NAME = f"missing-container-{faker.uuid4()}"
    container_details: dict[str, DockerContainer | None] = (
        await _get_containers_inspect_from_names(
            [*container_names, MISSING_CONTAINER_NAME]
        )
    )
    # containers which do not exist always return None
    assert MISSING_CONTAINER_NAME in container_details
    assert container_details.pop(MISSING_CONTAINER_NAME) is None

    assert set(container_details.keys()) == set(container_names)
    for docker_container in container_details.values():
        assert docker_container is not None


async def test_get_container_statuses(
    started_services: None, container_names: list[str], faker: Faker
):
    MISSING_CONTAINER_NAME = f"missing-container-{faker.uuid4()}"
    container_states: dict[str, ContainerState | None] = await get_container_states(
        [*container_names, MISSING_CONTAINER_NAME]
    )
    # containers which do not exist always have a None status
    assert MISSING_CONTAINER_NAME in container_states
    assert container_states.pop(MISSING_CONTAINER_NAME) is None

    assert set(container_states.keys()) == set(container_names)
    for docker_status in container_states.values():
        assert docker_status is not None


async def test_get_running_containers_count_from_names(
    started_services: None, container_names: list[str], container_count: PositiveInt
):
    found_containers = await get_containers_count_from_names(container_names)
    assert found_containers == container_count


COMPOSE_SPEC_SAMPLE = {
    "services": {
        "my-test-container": {
            "environment": [
                "DY_SIDECAR_PATH_INPUTS=/work/inputs",
                "DY_SIDECAR_PATH_OUTPUTS=/work/outputs",
                'DY_SIDECAR_STATE_PATHS=["/work/workspace"]',
            ],
            "working_dir": "/work",
            "image": "busybox:latest",
        },
        "my-test-container2": {
            "image": "nginx:latest",
        },
        "my-test-container3": {
            "image": "simcore/services/dynamic/jupyter-math:2.1.3",
        },
    },
}


@pytest.fixture
def compose_spec_yaml() -> str:
    return yaml.safe_dump(COMPOSE_SPEC_SAMPLE, indent=1)


def test_get_docker_service_images(compose_spec_yaml: str):
    assert get_docker_service_images(compose_spec_yaml) == {
        "busybox:latest",
        "nginx:latest",
        "simcore/services/dynamic/jupyter-math:2.1.3",
    }
