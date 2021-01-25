from enum import Enum
from pydantic import BaseModel, Field, PositiveInt
from typing import List


class ServiceSidecarStatus(str, Enum):
    OK = "ok"  # running as expected
    FAILING = "failing"  # requests to the sidecar API are failing service should be cosnidered as unavailable


class OverallStatus(BaseModel):

    status: ServiceSidecarStatus = Field(..., description="status of the service")
    info: str = Field(..., description="additional information for the user")

    def _update(self, new_status: ServiceSidecarStatus, new_info: str) -> None:
        self.status = new_status
        self.info = new_info

    def update_ok_status(self, info: str) -> None:
        self._update(ServiceSidecarStatus.OK, info)

    def update_failing_status(self, info: str) -> None:
        self._update(ServiceSidecarStatus.FAILING, info)

    def __eq__(self, other: "OverallStatus") -> bool:
        return self.status == other.status and self.info == other.info

    @classmethod
    def make_initially_ok(cls) -> "OverallStatus":
        # the service is initially ok when started
        initial_state = cls(status=ServiceSidecarStatus.OK, info="")
        return initial_state


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
    overall_status: OverallStatus = Field(
        OverallStatus.make_initially_ok(),
        description="status of the service sidecar also with additional information",
    )

    hostname: str = Field(..., description="docker hostname for this service")

    port: PositiveInt = Field(8000, description="service-sidecar port")

    is_available: bool = Field(
        False,
        scription="infroms if the web API on the service-sidecar is responding",
    )

    compose_spec_submitted: bool = Field(
        False,
        description="if the docker-compose spec was already submitted this fields is True",
    )

    are_containers_ready: bool = Field(
        False,
        description=(
            "if all started containers are in a ready state the service all "
            "is good and the service can receive requests"
        ),
    )

    # consider adding containers for healthchecks but this is more difficult and it depends on each service

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
    ) -> "MonitorData":
        payload = dict(
            service_name=service_name,
            service_sidecar=dict(
                hostname=hostname,
                port=port,
            ),
        )
        return cls.parse_obj(payload)