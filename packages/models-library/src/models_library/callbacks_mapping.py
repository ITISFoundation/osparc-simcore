from collections.abc import Sequence
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, field_validator

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
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"service": "rt-web", "command": "ls", "timeout": 1},
                {"service": "s4l-core", "command": ["ls", "-lah"], "timeout": 1},
            ]
        },
    )


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

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    # empty validates
                },
                {
                    "metrics": None,
                    "before_shutdown": [],
                },
                {"metrics": UserServiceCommand.model_config["json_schema_extra"]["examples"][0]},  # type: ignore [index]
                {
                    "metrics": UserServiceCommand.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "before_shutdown": [
                        UserServiceCommand.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                        UserServiceCommand.model_config["json_schema_extra"]["examples"][1],  # type: ignore [index]
                    ],
                },
                {
                    "metrics": UserServiceCommand.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                    "before_shutdown": [
                        UserServiceCommand.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                        UserServiceCommand.model_config["json_schema_extra"]["examples"][1],  # type: ignore [index]
                    ],
                    "inactivity": UserServiceCommand.model_config["json_schema_extra"]["examples"][0],  # type: ignore [index]
                },
            ]
        },
    )

    @field_validator("inactivity")
    @classmethod
    def ensure_inactivity_timeout_is_capped(
        cls, v: UserServiceCommand
    ) -> UserServiceCommand:
        if v is not None and (
            v.timeout < TIMEOUT_MIN or v.timeout > INACTIVITY_TIMEOUT_CAP
        ):
            msg = (
                f"Constraint not respected for inactivity timeout={v.timeout}: "
                f"interval=({TIMEOUT_MIN}, {INACTIVITY_TIMEOUT_CAP})"
            )
            raise ValueError(msg)
        return v
