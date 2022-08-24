from pydantic import ByteSize, Field, parse_obj_as
from settings_library.base import BaseCustomSettings


class ProjectsSettings(BaseCustomSettings):
    PROJECTS_MAX_COPY_SIZE_BYTES: ByteSize = Field(
        parse_obj_as(ByteSize, "30Gib"),
        description="defines the maximum authorized project data size when copying a project",
    )
