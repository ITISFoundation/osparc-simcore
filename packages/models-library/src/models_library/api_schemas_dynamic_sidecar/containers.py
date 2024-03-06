from typing import TypeAlias

from pydantic import BaseModel, NonNegativeFloat


class InactivityResponse(BaseModel):
    seconds_inactive: NonNegativeFloat | None = None

    @property
    def is_active(self) -> bool:
        return self.seconds_inactive is None


ServiceInactivityResponse: TypeAlias = InactivityResponse | None
