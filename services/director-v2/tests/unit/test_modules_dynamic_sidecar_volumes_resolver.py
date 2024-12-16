# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import os
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

import aiodocker
import pytest
from faker import Faker
from models_library.api_schemas_directorv2.services import (
    CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME,
)
from models_library.projects import ProjectID
from models_library.services import ServiceRunID
from models_library.users import UserID
from simcore_service_director_v2.modules.dynamic_sidecar.volumes import (
    DynamicSidecarVolumesPathsResolver,
)


@pytest.fixture(scope="session")
def swarm_stack_name() -> str:
    return "test_swarm_stack_name"


@pytest.fixture
def node_uuid(faker: Faker) -> UUID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def state_paths() -> list[Path]:
    return [Path(f"/tmp/asd/asd/{x}") for x in range(10)]


@pytest.fixture
def service_run_id() -> ServiceRunID:
    return ServiceRunID.create_for_dynamic_sidecar()


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return faker.uuid4(cast_to=None)


@pytest.fixture
def expected_volume_config(
    swarm_stack_name: str,
    node_uuid: UUID,
    service_run_id: ServiceRunID,
    project_id: ProjectID,
    user_id: UserID,
) -> Callable[[str, str], dict[str, Any]]:
    def _callable(source: str, target: str) -> dict[str, Any]:
        return {
            "Source": source,
            "Target": target,
            "Type": "volume",
            "VolumeOptions": {
                "DriverConfig": None,
                "Labels": {
                    "source": source,
                    "run_id": service_run_id,
                    "study_id": f"{project_id}",
                    "user_id": f"{user_id}",
                    "swarm_stack_name": swarm_stack_name,
                    "node_uuid": f"{node_uuid}",
                },
            },
        }

    return _callable


def test_expected_paths(
    swarm_stack_name: str,
    node_uuid: UUID,
    state_paths: list[Path],
    expected_volume_config: Callable[[str, str], dict[str, Any]],
    service_run_id: ServiceRunID,
    project_id: ProjectID,
    user_id: UserID,
) -> None:
    fake = Faker()

    inputs_path = Path(fake.file_path(depth=3)).parent
    assert DynamicSidecarVolumesPathsResolver.mount_entry(
        swarm_stack_name,
        inputs_path,
        node_uuid,
        service_run_id,
        project_id,
        user_id,
        None,
    ) == expected_volume_config(
        source=f"dyv_{service_run_id}_{node_uuid}_{f'{inputs_path}'.replace('/', '_')[::-1]}",
        target=str(Path("/dy-volumes") / inputs_path.relative_to("/")),
    )

    outputs_path = Path(fake.file_path(depth=3)).parent
    assert DynamicSidecarVolumesPathsResolver.mount_entry(
        swarm_stack_name,
        outputs_path,
        node_uuid,
        service_run_id,
        project_id,
        user_id,
        None,
    ) == expected_volume_config(
        source=f"dyv_{service_run_id}_{node_uuid}_{f'{outputs_path}'.replace('/', '_')[::-1]}",
        target=str(Path("/dy-volumes") / outputs_path.relative_to("/")),
    )

    for path in state_paths:
        name_from_path = f"{path}".replace(os.sep, "_")[::-1]
        assert DynamicSidecarVolumesPathsResolver.mount_entry(
            swarm_stack_name, path, node_uuid, service_run_id, project_id, user_id, None
        ) == expected_volume_config(
            source=f"dyv_{service_run_id}_{node_uuid}_{name_from_path}",
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
        service_run_id=ServiceRunID.create_for_dynamic_sidecar(),
    )

    await assert_creation_and_removal(unique_volume_name)


def test_volumes_get_truncated_as_expected(faker: Faker):
    node_uuid = faker.uuid4(cast_to=None)
    service_run_id = ServiceRunID.create_for_dynamic_sidecar()
    assert node_uuid != service_run_id
    unique_volume_name = DynamicSidecarVolumesPathsResolver.source(
        path=Path(
            f"/home/user/a-{'-'.join(['very' for _ in range(34)])}-long-home-path/workspace"
        ),
        node_uuid=node_uuid,
        service_run_id=service_run_id,
    )

    # if below fails the agent will have issues please check
    constant_part = unique_volume_name[: CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME - 1]
    assert constant_part == f"dyv_{service_run_id}_{node_uuid}"

    assert len(unique_volume_name) == 255
    assert f"{service_run_id}" in unique_volume_name
    assert f"{node_uuid}" in unique_volume_name
