from datetime import datetime
from enum import auto
from pathlib import Path

import aiofiles
import arrow
from pydantic import BaseModel, Field

from .enum_utils import StrAutoEnum


class VolumeStatus(StrAutoEnum):
    CONTENT_NEEDS_TO_BE_SAVED = auto()
    CONTENT_WAS_SAVED = auto()
    CONTENT_NO_SAVE_REQUIRED = auto()


class VolumeState(BaseModel):
    status: VolumeStatus
    last_changed: datetime = Field(default_factory=lambda: arrow.utcnow().datetime)

    def __eq__(self, other: "VolumeState") -> bool:
        # only include status for equality last_changed is not important
        return self.status == other.status


async def load_volume_state(agent_file_path: Path) -> VolumeState:
    async with aiofiles.open(agent_file_path, mode="r") as f:
        return VolumeState.parse_raw(await f.read())


async def save_volume_state(agent_file_path: Path, volume_state: VolumeState) -> None:
    async with aiofiles.open(agent_file_path, mode="w") as f:
        await f.write(volume_state.json())
