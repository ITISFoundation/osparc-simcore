from pydantic import BaseModel, NonNegativeFloat, validator


class InactivityResponse(BaseModel):
    supports_inactivity: bool
    seconds_inactive: NonNegativeFloat | None = None

    @validator("seconds_inactive", always=True)
    @classmethod
    def ensure_seconds_inactive_is_set_correctly(cls, v, values):
        if v is None and values["supports_inactivity"] is True:
            msg = "When seconds_inactive is None, supports_inactivity must be False"
            raise ValueError(msg)

        if v is not None and values["supports_inactivity"] is False:
            msg = "When seconds_inactive is not None, supports_inactivity must be True"
            raise ValueError(msg)

        return v
