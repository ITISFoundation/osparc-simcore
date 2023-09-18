from collections.abc import Sequence
from typing import Any, ClassVar

from pydantic import BaseModel, Field, NonNegativeFloat


class UserServiceCommand(BaseModel):
    service: str = Field(
        ..., description="name of the docker-compose service in the docker-compose spec"
    )
    command: str | Sequence[str] = Field(..., description="command to run in container")
    timeout: NonNegativeFloat = Field(
        ..., description="after this interval the command will be timed-out"
    )

    class Config:
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

    class Config:
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
            ]
        }
