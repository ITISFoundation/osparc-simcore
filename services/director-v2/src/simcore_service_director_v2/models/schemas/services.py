from enum import Enum
from typing import List, Optional

from models_library.basic_types import PortInt
from models_library.projects_nodes_io import UUID_REGEX
from models_library.services import KEY_RE, VERSION_RE, ServiceDockerData
from pydantic import BaseModel, Field, constr


class NodeRequirement(str, Enum):
    CPU = "CPU"
    GPU = "GPU"
    MPI = "MPI"


class ServiceBuildDetails(BaseModel):
    build_date: str
    vcs_ref: str
    vcs_url: str


class ServiceExtras(BaseModel):
    node_requirements: List[NodeRequirement]
    service_build_details: Optional[ServiceBuildDetails]


class ServiceExtrasEnveloped(BaseModel):
    data: ServiceExtras


class ServiceState(str, Enum):
    PENDING = "pending"
    PULLING = "pulling"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class RunningServiceDetails(BaseModel):
    published_port: Optional[PortInt] = Field(
        ...,
        description="The ports where the service provides its interface on the docker swarm",
        deprecated=True,
    )
    entry_point: str = Field(
        ...,
        description="The entry point where the service provides its interface",
    )
    service_uuid: str = Field(
        ..., regex=UUID_REGEX, description="The node UUID attached to the service"
    )
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
    service_port: PortInt = Field(
        80, description="port to access the service within the network"
    )
    service_basepath: str = Field(
        ...,
        description="the service base entrypoint where the service serves its contents",
    )
    service_state: ServiceState = Field(
        ...,
        description="the service state * 'pending' - The service is waiting for resources to start * 'pulling' - The service is being pulled from the registry * 'starting' - The service is starting * 'running' - The service is running * 'complete' - The service completed * 'failed' - The service failed to start\n",
    )
    service_message: str = Field(..., description="the service message")


class RunningServicesDetailsArray(BaseModel):
    __root__: List[RunningServiceDetails]


class RunningServicesDetailsArrayEnveloped(BaseModel):
    data: RunningServicesDetailsArray


class RunningServiceDetailsEnveloped(BaseModel):
    data: RunningServiceDetails


class ServicesArrayEnveloped(BaseModel):
    data: List[ServiceDockerData]
