from enum import Enum, unique
from pathlib import Path
from typing import Optional

from models_library.basic_types import PortInt
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import DYNAMIC_SERVICE_KEY_RE, VERSION_RE
from pydantic import BaseModel, Field

from .constants import UserID


class DynamicServiceBase(BaseModel):
    user_id: UserID
    project_id: ProjectID
    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=DYNAMIC_SERVICE_KEY_RE,
        examples=[
            "simcore/services/dynamic/3dviewer",
        ],
    )
    version: str = Field(
        ...,
        description="semantic version number of the node",
        regex=VERSION_RE,
        examples=["1.0.0", "0.0.1"],
    )
    uuid: NodeID
    basepath: Path = Field(
        ...,
        description="predefined path where the dynamic service should be served. If empty, the service shall use the root endpoint.",
    )

    class Config:
        schema_extra = {
            "example": {
                "user_id": 234,
                "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                "key": "simcore/services/dynamic/3dviewer",
                "version": "2.4.5",
                "uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
            }
        }


@unique
class ServiceState(str, Enum):
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class DynamicServiceState(DynamicServiceBase):
    host: str = Field(..., description="the service swarm internal host name")
    internal_port: PortInt = Field(..., description="the service swarm internal port")
    published_port: PortInt = Field(
        ..., description="the service swarm published port if any"
    )
    entry_point: Optional[str] = Field(
        None, description="if empty the service entrypoint is on the root endpoint."
    )

    state: ServiceState = Field(..., description="service current state")
    message: Optional[str] = Field(
        None, description="additional information related to service state"
    )
