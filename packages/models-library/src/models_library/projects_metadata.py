from datetime import datetime
from typing import Any

from pydantic import BaseModel

from .projects import ProjectID


class ProjectsMetadataDBGet(BaseModel):
    project_uuid: ProjectID
    custom: dict[str, Any]
    created: datetime
    modified: datetime
    parent_project_uuid: ProjectID
    parent_node_id: ProjectID
    root_parent_project_uuid: ProjectID
    root_parent_node_id: ProjectID
