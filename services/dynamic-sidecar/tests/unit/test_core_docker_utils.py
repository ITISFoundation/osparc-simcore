# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import suppress
from typing import Any

import aiodocker
import pytest
import yaml
from aiodocker.containers import DockerContainer
from faker import Faker
from models_library.generated_models.docker_rest_api import ContainerState
from models_library.services import RunID
from pydantic import PositiveInt, SecretStr, parse_obj_as
from settings_library.docker_registry import RegistrySettings
from simcore_service_dynamic_sidecar.core.docker_utils import (
    _DockerProgressDict,
    _get_containers_inspect_from_names,
    _parse_docker_pull_progress,
    get_container_states,
    get_containers_count_from_names,
    get_docker_service_images,
    get_volume_by_label,
    pull_images,
)
from simcore_service_dynamic_sidecar.core.errors import VolumeNotFoundError


@pytest.fixture
def volume_name() -> str:
    return "test_source_name"


@pytest.fixture
def run_id() -> RunID:
    return RunID.create()


@pytest.fixture
async def volume_with_label(volume_name: str, run_id: RunID) -> AsyncIterable[None]:
    async with aiodocker.Docker() as docker_client:
        volume = await docker_client.volumes.create(
            {
                "Name": "test_volume_name_1",
                "Labels": {"source": volume_name, "run_id": run_id},
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
            with suppress(aiodocker.DockerError):
                await container.kill()
            await container.delete()


async def test_volume_with_label(
    volume_with_label: None, volume_name: str, run_id: RunID
) -> None:
    assert await get_volume_by_label(volume_name, run_id)


async def test_volume_label_missing(run_id: RunID) -> None:
    with pytest.raises(VolumeNotFoundError) as exc_info:
        await get_volume_by_label("not_exist", run_id)

    error_msg = f"{exc_info.value}"
    assert run_id in error_msg
    assert "not_exist" in error_msg


async def test__get_containers_inspect_from_names(
    started_services: None, container_names: list[str], faker: Faker
):
    MISSING_CONTAINER_NAME = f"missing-container-{faker.uuid4()}"
    container_details: dict[
        str, DockerContainer | None
    ] = await _get_containers_inspect_from_names(
        [*container_names, MISSING_CONTAINER_NAME]
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
    "version": "3.8",
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


@pytest.mark.skip(
    reason="Only for manual testing."
    "Avoid this test in CI since it consumes disk and time"
)
async def test_issue_3793_pulling_images_raises_error():
    """
    Reproduces (sometimes) https://github.com/ITISFoundation/osparc-simcore/issues/3793
    """

    async def _print_progress(*args, **kwargs) -> None:
        print("progress -> ", args, kwargs)

    async def _print_log(*args, **kwargs) -> None:
        print("log -> ", args, kwargs)

    for n in range(2):
        await pull_images(
            images={
                "ubuntu:latest",
                "ubuntu:18.04",
                "ubuntu:22.04",
                "ubuntu:22.10",
                "ubuntu:23.04",
                "ubuntu:14.04",
                "itisfoundation/mattward-viewer:latest",  # 6.1 GB
            },
            registry_settings=RegistrySettings(
                REGISTRY_AUTH=False,
                REGISTRY_USER="",
                REGISTRY_PW=SecretStr(""),
                REGISTRY_SSL=False,
            ),
            progress_cb=_print_progress,
            log_cb=_print_log,
        )


@pytest.mark.parametrize("repeat", ["first-pull", "repeat-pull"])
async def test_pull_image(repeat: str):
    async def _print_progress(current: int, total: int):
        print("progress ->", f"{current=}", f"{total=}")

    async def _print_log(msg, log_level):
        assert "alpine" in msg
        print(f"log: {log_level=}: {msg}")

    await pull_images(
        images={
            "alpine:latest",
        },
        registry_settings=RegistrySettings(
            REGISTRY_AUTH=False,
            REGISTRY_USER="",
            REGISTRY_PW=SecretStr(""),
            REGISTRY_SSL=False,
        ),
        progress_cb=_print_progress,
        log_cb=_print_log,
    )


PULL_PROGRESS_SEQUENCE: list[dict[str, Any]] = [
    {"status": "Pulling from library/busybox", "id": "latest"},
    {"status": "Pulling fs layer", "progressDetail": {}, "id": "3f4d90098f5b"},
    {
        "status": "Downloading",
        "progressDetail": {"current": 22621, "total": 2219949},
        "progress": "[>                                                  ]  22.62kB/2.22MB",
        "id": "3f4d90098f5b",
    },
    {"status": "Download complete", "progressDetail": {}, "id": "3f4d90098f5b"},
    {
        "status": "Extracting",
        "progressDetail": {"current": 32768, "total": 2219949},
        "progress": "[>                                                  ]  32.77kB/2.22MB",
        "id": "3f4d90098f5b",
    },
    {
        "status": "Extracting",
        "progressDetail": {"current": 884736, "total": 2219949},
        "progress": "[===================>                               ]  884.7kB/2.22MB",
        "id": "3f4d90098f5b",
    },
    {
        "status": "Extracting",
        "progressDetail": {"current": 2219949, "total": 2219949},
        "progress": "[==================================================>]   2.22MB/2.22MB",
        "id": "3f4d90098f5b",
    },
    {"status": "Pull complete", "progressDetail": {}, "id": "3f4d90098f5b"},
    {
        "status": "Digest: sha256:3fbc632167424a6d997e74f52b878d7cc478225cffac6bc977eedfe51c7f4e79"
    },
    {
        "status": "Digest: sha256:3fbc632167424a6d997e74f52b878d7cc478225cffac6bc977eedfe51c7f4e79"
    },
    {"status": "Status: Downloaded newer image for busybox:latest"},
]


@pytest.mark.parametrize("pull_progress", PULL_PROGRESS_SEQUENCE)
def test_docker_progress_dict(pull_progress: dict[str, Any]):
    assert parse_obj_as(_DockerProgressDict, pull_progress)


def test__parse_docker_pull_progress():
    some_data = {}
    for entry in PULL_PROGRESS_SEQUENCE:
        _parse_docker_pull_progress(parse_obj_as(_DockerProgressDict, entry), some_data)
