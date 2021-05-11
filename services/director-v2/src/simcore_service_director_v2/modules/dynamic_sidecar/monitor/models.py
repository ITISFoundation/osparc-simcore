import datetime
import logging
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, PositiveInt

from .utils import AsyncResourceLock
from ....models.domains.dynamic_sidecar import PathsMappingModel, ComposeSpecModel
from models_library.services import SERVICE_KEY_RE
from models_library.basic_regex import VERSION_RE
from ..parse_docker_status import ServiceState

logger = logging.getLogger()


class DynamicSidecarStatus(str, Enum):
    OK = "ok"  # running as expected
    FAILING = "failing"  # requests to the sidecar API are failing service should be cosnidered as unavailable


class OverallStatus(BaseModel):
    """Generated from data from docker container inspect API"""

    status: DynamicSidecarStatus = Field(..., description="status of the service")
    info: str = Field(..., description="additional information for the user")

    def _update(self, new_status: DynamicSidecarStatus, new_info: str) -> None:
        self.status = new_status
        self.info = new_info

    def update_ok_status(self, info: str) -> None:
        self._update(DynamicSidecarStatus.OK, info)

    def update_failing_status(self, info: str) -> None:
        self._update(DynamicSidecarStatus.FAILING, info)

    def __eq__(self, other: "OverallStatus") -> bool:
        return self.status == other.status and self.info == other.info

    @classmethod
    def make_initially_ok(cls) -> "OverallStatus":
        # the service is initially ok when started
        initial_state = cls(status=DynamicSidecarStatus.OK, info="")
        return initial_state


class DockerStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"


class DockerContainerInspect(BaseModel):
    # TODO: add other information which makes sense to store
    status: DockerStatus = Field(
        ...,
        scription="status of the underlying container",
    )
    name: str = Field(..., description="docker name of the container")
    id: str = Field(..., description="docker id of the container")

    last_updated: datetime.datetime = Field(
        default_factory=datetime.datetime.utcnow,
        description="time of the update in UTC",
    )


class DynamicSidecar(BaseModel):
    overall_status: OverallStatus = Field(
        OverallStatus.make_initially_ok(),
        description="status of the service sidecar also with additional information",
    )

    hostname: str = Field(..., description="docker hostname for this service")

    port: PositiveInt = Field(8000, description="dynamic-sidecar port")

    is_available: bool = Field(
        False,
        scription=(
            "is True while the health check on the dynamic-sidecar is responding. "
            "Meaning that the dynamic-sidecar is reachable and can accept requests"
        ),
    )

    @property
    def compose_spec_submitted(self) -> bool:
        """
        If the director-v2 is rebooted was_compose_spec_submitted is False
        If the compose-spec is submitted it can be safely assumed that the
        containers_inspect contains some elements.
        """
        return self.was_compose_spec_submitted or len(self.containers_inspect)

    was_compose_spec_submitted: bool = Field(
        False,
        description="if the docker-compose spec was already submitted this fields is True",
    )

    containers_inspect: List[DockerContainerInspect] = Field(
        [],
        scription="docker inspect results from all the container ran at regular intervals",
    )

    # consider adding containers for healthchecks but this is more difficult and it depends on each service

    @property
    def endpoint(self):
        """endpoint where all the services are exposed"""
        return f"http://{self.hostname}:{self.port}"

    @property
    def are_containers_ready(self) -> bool:
        """returns: True if all containers are in running state"""
        return all(
            docker_container_inspect.status == DockerStatus.RUNNING
            for docker_container_inspect in self.containers_inspect
        )


class MonitorData(BaseModel):
    service_name: str = Field(
        ..., description="Name of the current dynamic-sidecar being monitored"
    )

    dynamic_sidecar: DynamicSidecar = Field(
        ...,
        description="stores information fetched from the dynamic-sidecar",
    )

    service_key: str = Field(
        ...,
        regex=SERVICE_KEY_RE,
        description="together with the tag used to compose the docker-compose spec for the service",
    )
    service_tag: str = Field(
        ...,
        regex=VERSION_RE,
        description="together with the key used to compose the docker-compose spec for the service",
    )
    paths_mapping: PathsMappingModel = Field(
        ...,
        description=(
            "the service explicitly requests where to mount all paths "
            "which will be handeled by the dynamic-sidecar"
        ),
    )
    compose_spec: ComposeSpecModel = Field(
        ...,
        description=(
            "if the user provides a compose_spec, it will be used instead "
            "of compsing one from the service_key and service_tag"
        ),
    )
    target_container: Optional[str] = Field(
        ...,
        description="when the user defines a compose spec, it should pick a container inside the spec to receive traffic on a defined port",
    )

    dynamic_sidecar_network_name: str = Field(
        ...,
        description="overlay network biding the proxy to the container spaned by the dynamic-sidecar",
    )

    simcore_traefik_zone: str = Field(
        ...,
        description="required for Traefik to correctly route requests to the spawned container",
    )
    service_port: PositiveInt = Field(
        ..., description="port where the service is exposed defined by the service"
    )

    @classmethod
    def assemble(
        # pylint: disable=too-many-arguments
        cls,
        service_name: str,
        hostname: str,
        port: int,
        service_key: str,
        service_tag: str,
        paths_mapping: PathsMappingModel,
        compose_spec: ComposeSpecModel,
        target_container: Optional[str],
        dynamic_sidecar_network_name: str,
        simcore_traefik_zone: str,
        service_port: int,
    ) -> "MonitorData":
        payload = dict(
            service_name=service_name,
            service_key=service_key,
            service_tag=service_tag,
            paths_mapping=paths_mapping,
            compose_spec=compose_spec,
            target_container=target_container,
            dynamic_sidecar_network_name=dynamic_sidecar_network_name,
            simcore_traefik_zone=simcore_traefik_zone,
            service_port=service_port,
            dynamic_sidecar=dict(
                hostname=hostname,
                port=port,
            ),
        )
        return cls.parse_obj(payload)


class LockWithMonitorData(BaseModel):
    """Used to wrap the """

    # locking is required to guarantee the monitoring will not be triggered
    # twice in a row for the service
    resource_lock: AsyncResourceLock = Field(
        ...,
        description=(
            "needed to exclude the service from a monitoring cycle while another "
            "monitoring cycle is already running"
        ),
    )

    monitor_data: MonitorData = Field(
        ..., description="required data used to monitor the dynamic-sidecar"
    )

    class Config:
        arbitrary_types_allowed = True


class ServiceStateReply(BaseModel):
    dynamic_type: str = Field(
        "dynamic-sidecar",
        description="tells the frontend this is run with a dynamic sidecar",
    )
    service_state: str = Field(..., description="refer to ")
    service_message: str = Field(
        ..., description="used to transmit error messages to the user"
    )

    published_port: Optional[int] = Field(..., description="the proxy's default port")

    service_uuid: Optional[str] = Field(
        ..., description="equals to the node_uuid value"
    )

    service_key: Optional[str] = Field(
        ..., description="starte service image service_key"
    )
    service_version: Optional[str] = Field(
        ..., description="starte service image service_version"
    )

    service_host: Optional[str] = Field(
        ...,
        description="using the dynamic-sidecar's host",
    )
    service_port: Optional[str] = Field(
        ..., description="using the dynamic-sidecar's port"
    )

    service_basepath: Optional[str] = Field(
        ..., description="not used by the dynamic-sidecar"
    )
    entry_point: Optional[str] = Field(
        ..., description="can be removed when dynamic_type='dynamic-sidecar'"
    )

    @classmethod
    def error_status(cls, node_uuid: str) -> "ServiceStateReply":
        error_status = ServiceStateReply(
            dynamic_type="dynamic-sidecar",
            service_state="error",
            service_message=f"Could not find a service for node_uuid={node_uuid}",
        )
        logging.warning(
            "Producting error status for dynamic-sidecar with node_uuid=%s\n%s",
            node_uuid,
            error_status,
        )
        return error_status

    @classmethod
    def make_status(
        cls,
        node_uuid: str,
        monitor_data: MonitorData,
        service_state: ServiceState,
        service_message: str,
    ) -> "ServiceStateReply":
        return cls(
            dynamic_type="dynamic-sidecar",
            published_port=80,
            entry_point="",
            service_uuid=node_uuid,
            service_key=monitor_data.service_key,
            service_version=monitor_data.service_tag,
            service_host=monitor_data.service_name,
            service_port=monitor_data.service_port,
            service_basepath="",
            service_state=service_state.value,
            service_message=service_message,
        )

    class Config:
        exclude_unset = True