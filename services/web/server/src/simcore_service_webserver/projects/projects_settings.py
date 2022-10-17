from pydantic import ByteSize, Field, NonNegativeInt, parse_obj_as
from settings_library.base import BaseCustomSettings


class ProjectsSettings(BaseCustomSettings):
    PROJECTS_MAX_COPY_SIZE_BYTES: ByteSize = Field(
        parse_obj_as(ByteSize, "30Gib"),
        description="defines the maximum authorized project data size"
        " when copying a project (disable with 0)",
    )
    PROJECTS_MAX_AUTO_STARTED_DYNAMIC_NODES_PRE_PROJECT: NonNegativeInt = Field(
        default=3,
        description="defines the number of dynamic services in a project that can be started concurrently",
    )
