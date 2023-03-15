# pylint: disable=redefined-outer-name

from pathlib import Path

import pytest
from faker import Faker
from servicelib.volumes_utils import VolumeState, load_volume_state
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes
from simcore_service_dynamic_sidecar.modules.volume_files import (
    AGENT_FILE_NAME,
    create_agent_file_on_all_volumes,
    create_hidden_file_on_all_volumes,
    set_volume_state_in_agent_file_outputs_saved,
    set_volume_state_in_agent_file_states_saved,
)


@pytest.fixture
def mounted_volumes(tmp_path: Path, faker: Faker) -> MountedVolumes:
    return MountedVolumes(
        run_id=faker.uuid4(cast_to=None),
        node_id=faker.uuid4(cast_to=None),
        inputs_path=tmp_path / "inputs",
        outputs_path=tmp_path / "outputs",
        state_paths=[tmp_path / "state"],
        state_exclude=set(),
        shared_store_path=tmp_path / "shared_store",
        compose_namespace="test",
        dy_volumes=Path("/"),
    )


async def test_create_hidden_file_on_all_volumes(mounted_volumes: MountedVolumes):
    await create_hidden_file_on_all_volumes(mounted_volumes)


async def test_create_agent_file_on_all_volumes(mounted_volumes: MountedVolumes):
    await create_agent_file_on_all_volumes(mounted_volumes)

    paths_to_check: list[Path] = list(mounted_volumes.disk_state_paths()) + [
        mounted_volumes.disk_outputs_path
    ]

    for path in paths_to_check:
        assert await load_volume_state(path / AGENT_FILE_NAME) == VolumeState(
            requires_saving=True, was_saved=False
        )

    # mark as saved
    await set_volume_state_in_agent_file_outputs_saved(mounted_volumes)
    await set_volume_state_in_agent_file_states_saved(mounted_volumes)

    # ensure these paths required saving and were saved
    for path in paths_to_check:
        assert await load_volume_state(path / AGENT_FILE_NAME) == VolumeState(
            requires_saving=True, was_saved=True
        )

    # ensure these paths do not require to be saved nor they were saved
    for path in (
        mounted_volumes.disk_inputs_path,
        mounted_volumes.disk_shared_store_path,
    ):
        assert await load_volume_state(path / AGENT_FILE_NAME) == VolumeState(
            requires_saving=False, was_saved=None
        )
