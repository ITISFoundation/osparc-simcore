from pydantic import BaseModel, NonNegativeFloat


class InactivityResponse(BaseModel):
    seconds_inactive: NonNegativeFloat | None = None

    @property
    def is_inactive(self) -> bool:
        return self.seconds_inactive is not None
