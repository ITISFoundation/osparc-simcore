from enum import Enum
from pydantic import BaseModel, Field
from typing import List


class DockerStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"


class StartedContainer(BaseModel):
    status: DockerStatus = Field(
        ...,
        scription="status of the underlying container",
    )


class ServiceSidecar(BaseModel):
    is_available: bool = Field(
        False,
        scription="infroms if the web API on the service-sidecar is responding",
    )

    @classmethod
    def make_empty(cls):
        return cls()


class MonitorData(BaseModel):
    """Stores information on the current status of service-sidecar"""

    service_name: str = Field(
        ..., description="Name of the current sidecar-service being monitored"
    )

    service_sidecar_status: ServiceSidecar = Field(
        ServiceSidecar.make_empty(),
        description="stores information fetched from the service-sidecar",
    )

    started_containers: List[StartedContainer] = Field(
        [],
        scription="list of container's monitor data spaned from the service-sidecar",
    )

    @classmethod
    def assemble(cls, service_name: str):
        return cls(service_name=service_name)