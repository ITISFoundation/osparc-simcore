from enum import auto

from pydantic import BaseModel

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.utils.enums import StrAutoEnum


class MountActivityStatus(StrAutoEnum):
    FILES_UPLOAD_ONGOING = auto()
    FILES_UPLOAD_ENDED = auto()


class StatePathsStatus(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    status: MountActivityStatus
