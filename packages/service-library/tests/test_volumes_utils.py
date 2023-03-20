# pylint: disable=redefined-outer-name

from pathlib import Path
from typing import Optional

import pytest
from pydantic import ValidationError
from servicelib.volumes_utils import VolumeState, load_volume_state, save_volume_state


@pytest.fixture
def agent_file_path(tmp_path: Path) -> Path:
    return tmp_path / "fake_agent_file"


@pytest.mark.parametrize(
    "requires_saving, was_saved",
    [
        pytest.param(True, False, id="volume_needs_to_be_saved_by_the_agent"),
        pytest.param(True, True, id="volume_was_saved_agent_does_not_backup_data"),
        pytest.param(
            False, None, id="volume_does_not_require_Saving_agent_does_not_backup_data"
        ),
    ],
)
async def test_save_load_volume_state(
    agent_file_path: Path, requires_saving: bool, was_saved: Optional[bool]
):
    to_save_volume_state = VolumeState(
        requires_saving=requires_saving, was_saved=was_saved
    )
    await save_volume_state(agent_file_path, to_save_volume_state)
    assert await load_volume_state(agent_file_path) == to_save_volume_state


@pytest.mark.parametrize(
    "requires_saving, was_saved",
    [
        (True, None),
        (False, True),
        (False, False),
    ],
)
def test_raises_validation_error(requires_saving: bool, was_saved: Optional[bool]):
    with pytest.raises(ValidationError):
        VolumeState(requires_saving=requires_saving, was_saved=was_saved)
