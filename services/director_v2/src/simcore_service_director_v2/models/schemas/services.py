from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from ..constants import SERVICE_IMAGE_NAME_RE, VERSION_RE
from .image_meta import ImageMetaData


class ServiceType(str, Enum):
    computational = "computational"
    interactive = "interactive"


class NodeRequirement(Enum):
    CPU = "CPU"
    GPU = "GPU"


class ServiceBuildDetails(BaseModel):
    build_date: Optional[str] = None
    vcs_ref: Optional[str] = None
    vcs_url: Optional[str] = None


class ServiceExtras(BaseModel):
    node_requirements: List[NodeRequirement]
    service_build_details: Optional[ServiceBuildDetails] = None


class ServiceExtrasEnveloped(BaseModel):
    data: ServiceExtras


class ServiceState(str, Enum):
    pending = "pending"
    pulling = "pulling"
    starting = "starting"
    running = "running"
    complete = "complete"
    failed = "failed"


class RunningServiceType(BaseModel):
    published_port: int = Field(
        ..., description="The ports where the service provides its interface", ge=1.0
    )
    entry_point: Optional[str] = Field(
        None,
        description="The entry point where the service provides its interface if specified",
    )
    service_uuid: str = Field(..., description="The UUID attached to this service")
    service_key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=SERVICE_IMAGE_NAME_RE,
    )
    service_version: str = Field(
        ..., description="semantic version number", regex=VERSION_RE,
    )
    service_host: str = Field(..., description="service host name within the network")
    service_port: int = Field(
        ..., description="port to access the service within the network", ge=1.0
    )
    service_basepath: Optional[str] = Field(
        "",
        description="different base path where current service is mounted otherwise defaults to root",
    )
    service_state: ServiceState = Field(
        ...,
        description="the service state * 'pending' - The service is waiting for resources to start * 'pulling' - The service is being pulled from the registry * 'starting' - The service is starting * 'running' - The service is running * 'complete' - The service completed * 'failed' - The service failed to start\n",
    )
    service_message: Optional[str] = Field(None, description="the service message")


class RunningServicesArray(BaseModel):
    __root__: List[RunningServiceType]


class RunningServicesEnveloped(BaseModel):
    data: RunningServicesArray




class ServicesEnveloped(BaseModel):
    __root__: List[ImageMetaData]
