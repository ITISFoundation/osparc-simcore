from enum import Enum
from pydantic import BaseModel, Field, PositiveInt
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
    hostname: str = Field(..., description="docker hostname for this service")
    port: PositiveInt = Field(8000, description="service-sidecar port")
    is_available: bool = Field(
        False,
        scription="infroms if the web API on the service-sidecar is responding",
    )
    service_sidecar_proxy_id: str = Field(
        ...,
        description="id of the proxy docker service which exposes the service outside",
    )
    service_sidecar_id: str = Field(
        ..., description="id of the service-sidecar docker service"
    )

    @property
    def endpoint(self):
        """endpoint where all teh services are exposed"""
        return f"http://{self.hostname}:{self.port}"


class MonitorData(BaseModel):
    """Stores information on the current status of service-sidecar"""

    service_name: str = Field(
        ..., description="Name of the current sidecar-service being monitored"
    )

    service_sidecar: ServiceSidecar = Field(
        ...,
        description="stores information fetched from the service-sidecar",
    )

    started_containers: List[StartedContainer] = Field(
        [],
        scription="list of container's monitor data spaned from the service-sidecar",
    )

    @classmethod
    def assemble(
        cls,
        service_name: str,
        hostname: str,
        port: int,
        service_sidecar_proxy_id: str,
        service_sidecar_id: str,
    ) -> "MonitorData":
        payload = dict(
            service_name=service_name,
            service_sidecar=dict(
                hostname=hostname,
                port=port,
                service_sidecar_proxy_id=service_sidecar_proxy_id,
                service_sidecar_id=service_sidecar_id,
            ),
        )
        return cls.parse_obj(payload)