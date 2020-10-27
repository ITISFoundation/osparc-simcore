from enum import Enum
from typing import List, Optional

from models_library.services import KEY_RE, VERSION_RE, ServiceDockerData
from pydantic import BaseModel, Field, constr
from pydantic.types import UUID4, PositiveInt


class NodeRequirement(str, Enum):
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
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class RunningServiceType(BaseModel):
    published_port: PositiveInt = Field(
        ..., description="The ports where the service provides its interface"
    )
    entry_point: Optional[str] = Field(
        None,
        description="The entry point where the service provides its interface if specified",
    )
    service_uuid: UUID4 = Field(..., description="The UUID attached to this service")
    service_key: constr(regex=KEY_RE) = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    )
    service_version: constr(regex=VERSION_RE) = Field(
        ...,
        description="service version number",
        example=["1.0.0", "0.0.1"],
    )
    service_host: str = Field(..., description="service host name within the network")
    service_port: PositiveInt = Field(
        ..., description="port to access the service within the network"
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


class ServicesArrayEnveloped(BaseModel):
    data: List[ServiceDockerData]
