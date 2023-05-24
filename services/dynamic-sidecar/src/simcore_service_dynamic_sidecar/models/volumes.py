from datetime import datetime

import arrow
from models_library.volumes import VolumeStatus
from pydantic import BaseModel, Field


class VolumeState(BaseModel):
    status: VolumeStatus
    last_changed: datetime = Field(default_factory=lambda: arrow.utcnow().datetime)

    def __eq__(self, other: object) -> bool:
        # only include status for equality last_changed is not important
        is_equal: bool = self.status == getattr(other, "status", None)
        return is_equal
