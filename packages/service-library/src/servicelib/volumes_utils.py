from pathlib import Path
from typing import Final, Optional

import aiofiles
from pydantic import BaseModel, Field, root_validator

HIDDEN_FILE_NAME: Final[str] = ".hidden_do_not_remove"
AGENT_FILE_NAME: Final[str] = ".agent"


class VolumeState(BaseModel):
    requires_saving: bool = Field(
        ..., description="if True volume must be saved before closing the sidecar"
    )
    was_saved: Optional[bool] = Field(
        None, description="if True volume was saved when the sidecar is closed, if None"
    )

    @root_validator
    @classmethod
    def check_passwords_match(cls, values: dict) -> dict:
        requires_saving: bool = values["requires_saving"]
        was_saved: Optional[bool] = values["was_saved"]

        # requires_saving is False was_saved MUST be None
        if requires_saving is False and was_saved is not None:
            raise ValueError(f"When {requires_saving=}, was_saved must be None")

        # requires_saving is True was_saved cannot be None
        if requires_saving is True and was_saved is None:
            raise ValueError(f"When {requires_saving=}, was_saved must NOT be None")

        return values


async def load_volume_state(agent_file_path: Path) -> VolumeState:
    async with aiofiles.open(agent_file_path, mode="r") as f:
        return VolumeState.parse_raw(await f.read())


async def save_volume_state(agent_file_path: Path, volume_state: VolumeState) -> None:
    async with aiofiles.open(agent_file_path, mode="w") as f:
        await f.write(volume_state.json())
