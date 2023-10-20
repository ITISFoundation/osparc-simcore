from collections.abc import Sequence
from typing import Any, ClassVar, Final

from pydantic import BaseModel, Extra, Field, NonNegativeFloat, validator

INACTIVITY_TIMEOUT_CAP: Final[NonNegativeFloat] = 5
TIMEOUT_MIN: Final[NonNegativeFloat] = 1


class UserServiceCommand(BaseModel):
    service: str = Field(
        ..., description="name of the docker-compose service in the docker-compose spec"
    )
    command: str | Sequence[str] = Field(..., description="command to run in container")
    timeout: NonNegativeFloat = Field(
        ..., description="after this interval the command will be timed-out"
    )

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"service": "rt-web", "command": "ls", "timeout": 1},
                {"service": "s4l-core", "command": ["ls", "-lah"], "timeout": 1},
            ]
        }


class CallbacksMapping(BaseModel):
    metrics: UserServiceCommand | None = Field(
        None,
        description="command to recover prometheus metrics from a specific user service",
    )
    before_shutdown: list[UserServiceCommand] = Field(
        default_factory=list,
        description=(
            "commands to run before shutting down the user services"
            "commands get executed first to last, multiple commands for the same"
            "user services are allowed"
        ),
    )
    inactivity: UserServiceCommand | None = Field(
        None,
        description=(
            "command used to figure out for how much time the "
            "user service(s) were inactive for"
        ),
    )

    @validator("inactivity")
    @classmethod
    def ensure_inactivity_timeout_is_capped(
        cls, v: UserServiceCommand
    ) -> UserServiceCommand:
        if v.timeout < TIMEOUT_MIN or v.timeout > INACTIVITY_TIMEOUT_CAP:
            msg = (
                f"Constraint not respected for inactivity timeout={v.timeout}: "
                f"interval=({TIMEOUT_MIN}, {INACTIVITY_TIMEOUT_CAP})"
            )
            raise ValueError(msg)
        return v

    class Config:
        extra = Extra.forbid
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    # empty validates
                },
                {
                    "metrics": None,
                    "before_shutdown": [],
                },
                {"metrics": UserServiceCommand.Config.schema_extra["examples"][0]},
                {
                    "metrics": UserServiceCommand.Config.schema_extra["examples"][0],
                    "before_shutdown": [
                        UserServiceCommand.Config.schema_extra["examples"][0],
                        UserServiceCommand.Config.schema_extra["examples"][1],
                    ],
                },
                {
                    "metrics": UserServiceCommand.Config.schema_extra["examples"][0],
                    "before_shutdown": [
                        UserServiceCommand.Config.schema_extra["examples"][0],
                        UserServiceCommand.Config.schema_extra["examples"][1],
                    ],
                    "inactivity": UserServiceCommand.Config.schema_extra["examples"][0],
                },
            ]
        }
