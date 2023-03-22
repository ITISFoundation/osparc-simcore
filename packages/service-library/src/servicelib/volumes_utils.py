from datetime import datetime

# PC: this block should be imported via:
# from models_library.utils.enums import StrAutoEnum
# from models_library.utils.enums import StrAutoEnum
from enum import Enum, auto, unique
from pathlib import Path

import aiofiles
import arrow
from pydantic import BaseModel, Field

###


@unique
class StrAutoEnum(str, Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.upper()


###


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
