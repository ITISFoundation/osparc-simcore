from datetime import datetime
from enum import Enum

from pydantic import BaseModel

from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..services import ServiceKey, ServiceVersion

# Frontend API


class ContainerStatus(str, Enum):
    RUNNING = "running"
    FINISHED = "finished"


class ContainerGet(BaseModel):
    project_uuid: ProjectID
    project_name: str | None
    node_uuid: NodeID
    node_label: str | None
    service_key: ServiceKey
    service_version: ServiceVersion
    start_time: datetime
    duration: float
    processors: float
    core_hours: float
    status: ContainerStatus
