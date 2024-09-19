from enum import StrEnum, auto

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServicePortKey
from pydantic import BaseModel


class OutputStatus(StrEnum):
    UPLOAD_STARTED = auto()
    UPLOAD_WAS_ABORTED = auto()
    UPLOAD_FINISHED_SUCCESSFULLY = auto()
    UPLOAD_FINISHED_WITH_ERRROR = auto()


class InputStatus(StrEnum):
    DOWNLOAD_STARTED = auto()
    DOWNLOAD_WAS_ABORTED = auto()
    DOWNLOAD_FINISHED_SUCCESSFULLY = auto()
    DOWNLOAD_FINISHED_WITH_ERRROR = auto()


class _PortStatusCommon(BaseModel):
    project_id: ProjectID
    node_id: NodeID
    port_key: ServicePortKey


class OutputPortStatus(_PortStatusCommon):
    status: OutputStatus


class InputPortSatus(_PortStatusCommon):
    status: InputStatus
