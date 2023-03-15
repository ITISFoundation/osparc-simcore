# pylint: disable=redefined-outer-name

from pathlib import Path
from typing import Optional

import pytest
from pydantic import ValidationError
from servicelib.volumes_utils import VolumeState, load_volume_state, save_volume_state


@pytest.fixture
def agent_file_path(tmpdir: Path) -> Path:
    return Path(tmpdir) / "fake_agent_file"


@pytest.mark.parametrize(
    "requires_saving, was_saved",
    [
        pytest.param(True, False, id="requires_saving_but_not_saved"),
        pytest.param(True, True, id="requires_saving_and_saved"),
        pytest.param(False, None, id="does_not_require_saving_no_save_action"),
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
