import datetime
from typing import Final

from pydantic import ByteSize, Field, NonNegativeFloat, NonNegativeInt, parse_obj_as
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

    PROJECTS_NODE_CREATE_INTERVAL: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=15),
        description="max time a node's start command should take on average",
    )

    @property
    def total_project_dynamic_nodes_creation_interval(self) -> NonNegativeFloat:
        """
        Estimated amount of time for all project node creation requests to be sent to the
        director-v2. Note: these calls are sent one after the other.
        """
        return (
            self.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES
            * self.PROJECTS_NODE_CREATE_INTERVAL.total_seconds()
        )
