from typing import TypeAlias

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel

_DB_KEY: TypeAlias = str


class CompTaskNotificationPayload(BaseModel):
    action: str
    changes: list[_DB_KEY]
    table: str
    task_id: int
    project_id: ProjectID
    node_id: NodeID
