from functools import cached_property
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..basic_types import PortInt
from ..projects import ProjectID
from ..projects_nodes_io import NodeID
from ..services import DynamicServiceKey, ServiceVersion
from ..services_enums import ServiceBootType, ServiceState
from ..users import UserID


class CommonServiceDetails(BaseModel):
    key: DynamicServiceKey = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        examples=[
            "simcore/services/dynamic/3dviewer",
        ],
        alias="service_key",
    )
    version: ServiceVersion = Field(
        ...,
        description="semantic version number of the node",
        examples=["1.0.0", "0.0.1"],
        alias="service_version",
    )

    user_id: UserID
    project_id: ProjectID
    node_uuid: NodeID = Field(..., alias="service_uuid")


class ServiceDetails(CommonServiceDetails):
    basepath: Path | None = Field(
        default=None,
        description="predefined path where the dynamic service should be served. If empty, the service shall use the root endpoint.",
        alias="service_basepath",
    )
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "key": "simcore/services/dynamic/3dviewer",
                "version": "2.4.5",
                "user_id": 234,
                "project_id": "dd1d04d9-d704-4f7e-8f0f-1ca60cc771fe",
                "node_uuid": "75c7f3f4-18f9-4678-8610-54a2ade78eaa",
                "basepath": "/x/75c7f3f4-18f9-4678-8610-54a2ade78eaa",
            }
        },
    )


class RunningDynamicServiceDetails(ServiceDetails):
    boot_type: ServiceBootType = Field(
        default=ServiceBootType.V0,
        description=(
            "Describes how the dynamic services was started (legacy=V0, modern=V2)."
            "Since legacy services do not have this label it defaults to V0."
        ),
    )

    host: str = Field(
        ..., description="the service swarm internal host name", alias="service_host"
    )
    internal_port: PortInt = Field(
        ..., description="the service swarm internal port", alias="service_port"
    )
    published_port: PortInt | None = Field(
        default=None,
        description="the service swarm published port if any",
        deprecated=True,
    )

    entry_point: str | None = Field(
        default=None,
        description="if empty the service entrypoint is on the root endpoint.",
        deprecated=True,
    )
    state: ServiceState = Field(
        ..., description="service current state", alias="service_state"
    )
    message: str | None = Field(
        default=None,
        description="additional information related to service state",
        alias="service_message",
    )

    model_config = ConfigDict(
        ignored_types=(cached_property,),
        json_schema_extra={
            "examples": [
                # legacy
                {
                    "service_key": "simcore/services/dynamic/raw-graphs",
                    "service_version": "2.10.6",
                    "user_id": 1,
                    "project_id": "32fb4eb6-ab30-11ef-9ee4-0242ac140008",
                    "service_uuid": "0cd049ba-cd6b-4a12-b416-a50c9bc8e7bb",
                    "service_basepath": "/x/0cd049ba-cd6b-4a12-b416-a50c9bc8e7bb",
                    "service_host": "raw-graphs_0cd049ba-cd6b-4a12-b416-a50c9bc8e7bb",
                    "service_port": 4000,
                    "published_port": None,
                    "entry_point": "",
                    "service_state": "running",
                    "service_message": "",
                },
                # new style
                {
                    "service_key": "simcore/services/dynamic/jupyter-math",
                    "service_version": "3.0.3",
                    "user_id": 1,
                    "project_id": "32fb4eb6-ab30-11ef-9ee4-0242ac140008",
                    "service_uuid": "6e3cad3a-eb64-43de-b476-9ac3c413fd9c",
                    "boot_type": "V2",
                    "service_host": "dy-sidecar_6e3cad3a-eb64-43de-b476-9ac3c413fd9c",
                    "service_port": 8888,
                    "service_state": "running",
                    "service_message": "",
                },
            ]
        },
    )

    @cached_property
    def legacy_service_url(self) -> str:
        return f"http://{self.host}:{self.internal_port}{self.basepath}"  # NOSONAR
