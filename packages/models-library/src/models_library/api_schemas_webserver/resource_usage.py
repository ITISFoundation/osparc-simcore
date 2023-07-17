from datetime import datetime
from enum import Enum

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from pydantic import BaseModel

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
