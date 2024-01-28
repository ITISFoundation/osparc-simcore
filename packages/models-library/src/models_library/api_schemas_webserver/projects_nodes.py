from typing import Literal

from pydantic import ConfigDict, Field

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
    service_id: str | None = None


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
        examples=[
            [
                "simcore/services/comp/itis/sleeper",
                "simcore/services/dynamic/3dviewer",
            ]
        ],
    )
    service_version: ServiceVersion = Field(
        ..., description="semantic version number", examples=[["1.0.0", "0.0.1"]]
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
    model_config = ConfigDict()


class NodeGetIdle(OutputSchema):
    service_state: Literal["idle"]
    service_uuid: NodeID

    @classmethod
    def from_node_id(cls, node_id: NodeID) -> "NodeGetIdle":
        return cls(service_state="idle", service_uuid=node_id)

    model_config = ConfigDict()


class NodeGetUnknown(OutputSchema):
    service_state: Literal["unknown"]
    service_uuid: NodeID

    @classmethod
    def from_node_id(cls, node_id: NodeID) -> "NodeGetUnknown":
        return cls(service_state="unknown", service_uuid=node_id)

    model_config = ConfigDict()


class NodeRetrieve(InputSchemaWithoutCameCase):
    port_keys: list[ServicePortKey] = []


class NodeRetrieved(RetrieveDataOut):
    # TODO[pydantic]: The `Config` class inherits from another class, please create the `model_config` manually.
    # Check https://docs.pydantic.dev/dev-v2/migration/#changes-to-config for more information.
    class Config(OutputSchema.Config):
        ...
