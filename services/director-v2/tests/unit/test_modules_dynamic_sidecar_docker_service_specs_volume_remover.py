# pylint: disable=redefined-outer-name

from pathlib import Path
from typing import AsyncIterator

import aiodocker
import pytest
from aiodocker.volumes import DockerVolume
from faker import Faker
from pydantic import parse_obj_as
from simcore_service_director_v2.modules.dynamic_sidecar.docker_service_specs.volume_remover import (
    SH_SCRIPT_REMOVE_VOLUMES,
    DockerVersion,
)

# UTILS


def _get_source(run_id: str, node_uuid: str, volume_path: Path) -> str:
    reversed_path = f"{volume_path}"[::-1].replace("/", "_")
    return f"dyv_{run_id}_{node_uuid}_{reversed_path}"


async def run_command(
    docker_version: DockerVersion, volume_names: list[str]
) -> list[str]:
    async with aiodocker.Docker() as docker_client:
        volume_names_seq = " ".join(volume_names)
        formatted_command = SH_SCRIPT_REMOVE_VOLUMES.format(
            volume_names_seq=volume_names_seq, retries=5, sleep=1
        )
        print("Container will run:\n%s", formatted_command)
        command = ["sh", "-c", formatted_command]

        container = await docker_client.containers.run(
            config={
                "Cmd": command,
                "Image": f"docker:{docker_version}-dind",
                "HostConfig": {"Binds": ["/var/run/docker.sock:/var/run/docker.sock"]},
            },
        )
        await container.start()
        await container.wait()

        logs = await container.log(stderr=True, stdout=True)

        await container.delete(force=True)

        return "".join(logs)


# FIXTURES


@pytest.fixture
def swarm_stack_name() -> str:
    return "test_stack"


@pytest.fixture
def study_id(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def node_uuid(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def run_id(faker: Faker) -> str:
    return faker.uuid4()


@pytest.fixture
def used_volume_path(tmp_path: Path) -> Path:
    return tmp_path / "used_volume"


@pytest.fixture
def unused_volume_path(tmp_path: Path) -> Path:
    return tmp_path / "unused_volume"


@pytest.fixture
async def unused_volume(
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
    unused_volume_path: Path,
) -> AsyncIterator[DockerVolume]:
    async with aiodocker.Docker() as docker_client:
        source = _get_source(run_id, node_uuid, unused_volume_path)
        volume = await docker_client.volumes.create(
            {
                "Name": source,
                "Labels": {
                    "node_uuid": node_uuid,
                    "run_id": run_id,
                    "source": source,
                    "study_id": study_id,
                    "swarm_stack_name": swarm_stack_name,
                    "user_id": "1",
                },
            }
        )

        # attach to volume and create some files!!!

        yield volume

        try:
            await volume.delete()
        except aiodocker.DockerError:
            pass


@pytest.fixture
async def used_volume(
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
    used_volume_path: Path,
) -> AsyncIterator[DockerVolume]:
    async with aiodocker.Docker() as docker_client:
        source = _get_source(run_id, node_uuid, used_volume_path)
        volume = await docker_client.volumes.create(
            {
                "Name": source,
                "Labels": {
                    "node_uuid": node_uuid,
                    "run_id": run_id,
                    "source": source,
                    "study_id": study_id,
                    "swarm_stack_name": swarm_stack_name,
                    "user_id": "1",
                },
            }
        )

        container = await docker_client.containers.run(
            config={
                "Cmd": ["/bin/ash", "-c", "sleep 10000"],
                "Image": "alpine:latest",
                "HostConfig": {"Binds": [f"{volume.name}:{used_volume_path}"]},
            },
            name=f"using_volume_{volume.name}",
        )
        await container.start()

        yield volume

        await container.delete(force=True)
        await volume.delete()


@pytest.fixture
async def used_volume_name(used_volume: DockerVolume) -> str:
    volume = await used_volume.show()
    return volume["Name"]


@pytest.fixture
async def unused_volume_name(unused_volume: DockerVolume) -> str:
    volume = await unused_volume.show()
    return volume["Name"]


@pytest.fixture
def missing_volume_name(run_id: str, node_uuid: str) -> str:
    return _get_source(run_id, node_uuid, Path("/MISSING/PATH"))


# TESTS


async def test_sh_script_error_if_volume_is_used(
    used_volume_name: str, docker_version: DockerVersion
):
    result = await run_command(docker_version, volume_names=[used_volume_name])
    assert "ERROR: Please check above logs, there was/were 1 error/s." in result


async def test_sh_script_removes_unused_volume(
    unused_volume_name: str, docker_version: DockerVersion
):
    result = await run_command(docker_version, volume_names=[unused_volume_name])
    assert "ERROR: Please check above logs, there was/were" not in result
    assert result == f"{unused_volume_name}\n"


async def test_sh_script_no_error_if_volume_does_not_exist(
    missing_volume_name: str, docker_version: DockerVersion
):
    result = await run_command(docker_version, volume_names=[missing_volume_name])
    assert "ERROR: Please check above logs, there was/were" not in result


@pytest.mark.parametrize(
    "docker_version",
    [
        "20.10.17",
        "20.10.17+azure-1-dind",  # github workers
        "20.10.17.",
        "20.10.17asdjasjsaddas",
    ],
)
def test_docker_version_strips_unwanted(docker_version: str):
    assert parse_obj_as(DockerVersion, docker_version) == "20.10.17"


@pytest.mark.parametrize(
    "invalid_docker_version",
    [
        "nope",
        ".20.10.17.",
        ".20.10.17",
    ],
)
def test_docker_version_invalid(invalid_docker_version: str):
    with pytest.raises(ValueError):
        parse_obj_as(DockerVersion, invalid_docker_version)
