from enum import auto

from pydantic import BaseModel, Field

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.utils.enums import StrAutoEnum


class MountActivityStatus(StrAutoEnum):
    FILES_UPLOAD_QUEUED = auto()
    FILES_UPLOAD_UPLOADING = auto()
    FILES_UPLOAD_QUEUED_AND_UPLOADING = auto()
    FILES_UPLOAD_ENDED = auto()


class StatePathsStatus(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    status: MountActivityStatus
    vfs_write_back_s: int = Field(
        description="Effective --vfs-write-back value in seconds from rclone mount settings",
    )
