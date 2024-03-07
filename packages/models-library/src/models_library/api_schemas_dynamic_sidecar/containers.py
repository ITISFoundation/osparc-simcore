from typing import TypeAlias

from pydantic import BaseModel, NonNegativeFloat


class InactivityResponse(BaseModel):
    seconds_inactive: NonNegativeFloat | None = None


ServiceInactivityResponse: TypeAlias = InactivityResponse | None
