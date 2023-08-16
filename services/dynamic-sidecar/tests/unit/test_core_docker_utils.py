# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
from collections.abc import AsyncIterable, AsyncIterator

import aiodocker
import pytest
import yaml
from aiodocker.containers import DockerContainer
from models_library.services import RunID
from pydantic import PositiveInt, SecretStr
from settings_library.docker_registry import RegistrySettings
from simcore_service_dynamic_sidecar.core.docker_utils import (
    _get_containers_details_from_names,
    get_containers_count_from_names,
    get_docker_service_images,
    get_volume_by_label,
    pull_images,
)
from simcore_service_dynamic_sidecar.core.errors import VolumeNotFoundError


@pytest.fixture(scope="session")
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
            container = await docker_client.containers.create(
                config={
                    "image": "alpine:latest",
                    "command": ["sh", "-c", "sleep 100000"],
                },
                name=container_name,
            )
            started_containers.append(container)

        yield

        for container in started_containers:
            await container.stop()
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


async def test_get_running_containers_details_from_names(
    started_services: None, container_names: list[str]
):
    if len(container_names) == 0:
        return

    containers: list[DockerContainer] = await _get_containers_details_from_names(
        container_names
    )
    for container in containers:
        assert container["State"]


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
