# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import os
from pathlib import Path
from typing import Any, Callable, Dict, List
from uuid import UUID

import aiodocker
import pytest
from faker import Faker
from simcore_service_director_v2.modules.dynamic_sidecar.volumes_resolver import (
    DynamicSidecarVolumesPathsResolver,
)

# FIXTURES


@pytest.fixture(scope="session")
def swarm_stack_name() -> str:
    return "test_swarm_stack_name"


@pytest.fixture
def node_uuid(faker: Faker) -> UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def state_paths() -> List[Path]:
    return [Path(f"/tmp/asd/asd/{x}") for x in range(10)]


@pytest.fixture
def run_id(faker: Faker) -> UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def expected_volume_config(
    swarm_stack_name: str, node_uuid: UUID, run_id: UUID
) -> Callable[[str, str], Dict[str, Any]]:
    def _callable(source: str, target: str) -> Dict[str, Any]:
        return {
            "Source": source,
            "Target": target,
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "source": source,
                    "run_id": f"{run_id}",
                    "swarm_stack_name": swarm_stack_name,
                    "uuid": f"{node_uuid}",
                }
            },
        }

    return _callable


# TESTS


def test_expected_paths(
    swarm_stack_name: str,
    node_uuid: UUID,
    state_paths: List[Path],
    expected_volume_config: Callable[[str, str], Dict[str, Any]],
    run_id: UUID,
) -> None:
    fake = Faker()

    inputs_path = Path(fake.file_path(depth=3)).parent
    assert DynamicSidecarVolumesPathsResolver.mount_entry(
        swarm_stack_name, inputs_path, node_uuid, run_id
    ) == expected_volume_config(
        source=f"dyv_{run_id}{f'{inputs_path}'.replace('/', '_')}_{node_uuid}",
        target=str(Path("/dy-volumes") / inputs_path.relative_to("/")),
    )

    outputs_path = Path(fake.file_path(depth=3)).parent
    assert DynamicSidecarVolumesPathsResolver.mount_entry(
        swarm_stack_name, outputs_path, node_uuid, run_id
    ) == expected_volume_config(
        source=f"dyv_{run_id}{f'{outputs_path}'.replace('/', '_')}_{node_uuid}",
        target=str(Path("/dy-volumes") / outputs_path.relative_to("/")),
    )

    for path in state_paths:
        name_from_path = f"{path}".replace(os.sep, "_")
        assert DynamicSidecarVolumesPathsResolver.mount_entry(
            swarm_stack_name, path, node_uuid, run_id
        ) == expected_volume_config(
            source=f"dyv_{run_id}{name_from_path}_{node_uuid}",
            target=str(Path("/dy-volumes/") / path.relative_to("/")),
        )


async def assert_creation_and_removal(volume_name: str) -> None:
    print(f"Ensure creation and removal of len={len(volume_name)} {volume_name=}")
    async with aiodocker.Docker() as client:
        named_volume = await client.volumes.create({"Name": volume_name})
        await named_volume.delete()


async def test_volumes_unique_name_max_length_can_be_created(
    faker: Faker, docker_swarm: None
):
    a_uuid = faker.uuid4()
    volume_name_len_255 = (a_uuid * 100)[:255]
    await assert_creation_and_removal(volume_name_len_255)


async def test_unique_name_creation_and_removal(faker: Faker):
    unique_volume_name = DynamicSidecarVolumesPathsResolver.source(
        path=Path("/some/random/path/to/a/workspace/folder"),
        node_uuid=faker.uuid4(cast_to=None),
        run_id=faker.uuid4(cast_to=None),
    )

    await assert_creation_and_removal(unique_volume_name)
