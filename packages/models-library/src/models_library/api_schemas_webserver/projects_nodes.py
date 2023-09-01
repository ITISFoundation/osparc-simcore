from typing import Any, ClassVar, Literal

from pydantic import Field

from ..api_schemas_directorv2.dynamic_services import RetrieveDataOut
from ..basic_types import PortInt
from ..projects_nodes_io import NodeID
from ..services import ServiceKey, ServicePortKey, ServiceVersion
from ..services_enums import ServiceState
from ..services_resources import ServiceResourcesDict
from ._base import InputSchemaWithoutCameCase, OutputSchema

assert ServiceResourcesDict  # nosec
__all__: tuple[str, ...] = ("ServiceResourcesDict",)


class NodeCreate(InputSchemaWithoutCameCase):
    service_key: ServiceKey
    service_version: ServiceVersion
    service_id: str | None


class NodeCreated(OutputSchema):
    node_id: NodeID


class NodeGet(OutputSchema):
    published_port: PortInt | None = Field(
        ...,
        description="The ports where the service provides its interface",
    )
    entry_point: str | None = Field(
        None,
        description="The entry point where the service provides its interface if specified",
    )
    service_uuid: str = Field(
        ...,
        description="The UUID attached to this service",
    )
    service_key: ServiceKey = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        example=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    )
    service_version: ServiceVersion = Field(
        ..., description="semantic version number", example=["1.0.0", "0.0.1"]
    )
    service_host: str = Field(
        ...,
        description="service host name within the network",
    )
    service_port: PortInt = Field(
        ..., description="port to access the service within the network"
    )
    service_basepath: str | None = Field(
        "",
        description="different base path where current service is mounted otherwise defaults to root",
    )
    service_state: ServiceState = Field(
        ...,
        description="the service state * 'pending' - The service is waiting for resources to start * 'pulling' - The service is being pulled from the registry * 'starting' - The service is starting * 'running' - The service is running * 'complete' - The service completed * 'failed' - The service failed to start\n",
    )
    service_message: str | None = Field(
        None,
        description="the service message",
    )
    user_id: str = Field(..., description="the user that started the service")

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "published_port": 30000,
                "entrypoint": "/the/entry/point/is/here",
                "service_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "service_key": "simcore/services/comp/itis/sleeper",
                "service_version": "1.2.3",
                "service_host": "jupyter_E1O2E-LAH",
                "service_port": 8081,
                "service_basepath": "/x/E1O2E-LAH",
                "service_state": "pending",
                "service_message": "no suitable node (insufficient resources on 1 node)",
                "user_id": 123,
            }
        }


class NodeGetIdle(OutputSchema):
    service_state: Literal["idle"]
    service_uuid: NodeID


class NodeRetrieve(InputSchemaWithoutCameCase):
    port_keys: list[ServicePortKey] = []


class NodeRetrieved(RetrieveDataOut):
    class Config(OutputSchema.Config):
        ...
