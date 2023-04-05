from typing import Final

from pydantic import ByteSize, Field, NonNegativeInt, parse_obj_as
from settings_library.base import BaseCustomSettings

_MINUTE: Final[int] = 60


class ProjectsSettings(BaseCustomSettings):
    PROJECTS_MAX_COPY_SIZE_BYTES: ByteSize = Field(
        parse_obj_as(ByteSize, "30Gib"),
        description="defines the maximum authorized project data size"
        " when copying a project (disable with 0)",
    )
    PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES: NonNegativeInt = Field(
        default=5,
        description="defines the number of dynamic services in a project that can be started concurrently (a value of 0 will disable it)",
    )

    PROJECTS_DYNAMIC_SERVICES_REDIS_LOCK_TIMEOUT_S: NonNegativeInt = Field(
        default=5 * _MINUTE,
        description="amount of time to wait for all the services inside a project (per user) to start",
    )
