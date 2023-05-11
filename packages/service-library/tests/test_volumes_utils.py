# pylint: disable=redefined-outer-name

from pathlib import Path

import pytest
from pytest import FixtureRequest
from servicelib.volumes_utils import (
    VolumeState,
    VolumeStatus,
    load_volume_state,
    save_volume_state,
)


@pytest.fixture
def agent_file_path(tmp_path: Path) -> Path:
    return tmp_path / "fake_agent_file"


@pytest.fixture(params=VolumeStatus)
def status(request: FixtureRequest) -> VolumeStatus:
    return request.param


async def test_save_load_volume_state(agent_file_path: Path, status: VolumeStatus):
    to_save_volume_state = VolumeState(status=status)
    await save_volume_state(agent_file_path, to_save_volume_state)
    assert await load_volume_state(agent_file_path) == to_save_volume_state


def test_volume_state_equality(status: VolumeStatus):
    assert VolumeState(status=status) == VolumeState(status=status)
    schema_property_count = len(VolumeState.schema()["properties"])
    assert len(VolumeState(status=status).dict()) == schema_property_count
