# mypy: disable-error-code=truthy-function
from typing import Any, Literal, TypeAlias

from pydantic import ConfigDict, Field

from ..api_schemas_directorv2.dynamic_services import RetrieveDataOut
from ..basic_types import PortInt
from ..projects_nodes import InputID, InputsDict
from ..projects_nodes_io import NodeID
from ..services import ServiceKey, ServicePortKey, ServiceVersion
from ..services_enums import ServiceState
from ..services_resources import ServiceResourcesDict
from ._base import InputSchemaWithoutCamelCase, OutputSchema

assert ServiceResourcesDict  # nosec
__all__: tuple[str, ...] = ("ServiceResourcesDict",)


class NodeCreate(InputSchemaWithoutCamelCase):
    service_key: ServiceKey
    service_version: ServiceVersion
    service_id: str | None = None


BootOptions: TypeAlias = dict


class NodePatch(InputSchemaWithoutCamelCase):
    service_key: ServiceKey | None = Field(default=None, alias="key")
    service_version: ServiceVersion | None = Field(default=None, alias="version")
    label: str | None = Field(default=None)
    inputs: InputsDict = Field(default=None)
    inputs_required: list[InputID] | None = Field(default=None, alias="inputsRequired")
    input_nodes: list[NodeID] | None = Field(default=None, alias="inputNodes")
    progress: float | None = Field(
        default=None, ge=0, le=100
    )  # NOTE: it is used by frontend for File Picker progress
    boot_options: BootOptions | None = Field(default=None, alias="bootOptions")
    outputs: dict[str, Any] | None = Field(
        default=None
    )  # NOTE: it is used by frontend for File Picker


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
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
        ],
    )
    service_version: ServiceVersion = Field(
        ..., description="semantic version number", examples=["1.0.0", "0.0.1"]
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
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                # computational
                {
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
                    "user_id": "123",
                },
                # dynamic
                {
                    "published_port": 30000,
                    "entrypoint": "/the/entry/point/is/here",
                    "service_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "service_key": "simcore/services/dynamic/some-dynamic-service",
                    "service_version": "1.2.3",
                    "service_host": "jupyter_E1O2E-LAH",
                    "service_port": 8081,
                    "service_basepath": "/x/E1O2E-LAH",
                    "service_state": "pending",
                    "service_message": "no suitable node (insufficient resources on 1 node)",
                    "user_id": "123",
                },
            ]
        }
    )


class NodeGetIdle(OutputSchema):
    service_state: Literal["idle"]
    service_uuid: NodeID

    @classmethod
    def from_node_id(cls, node_id: NodeID) -> "NodeGetIdle":
        return cls(service_state="idle", service_uuid=node_id)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "service_state": "idle",
            }
        }
    )


class NodeGetUnknown(OutputSchema):
    service_state: Literal["unknown"]
    service_uuid: NodeID

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "service_state": "unknown",
            }
        }
    )

    @classmethod
    def from_node_id(cls, node_id: NodeID) -> "NodeGetUnknown":
        return cls(service_state="unknown", service_uuid=node_id)


class NodeOutputs(InputSchemaWithoutCamelCase):
    outputs: dict[str, Any]


class NodeRetrieve(InputSchemaWithoutCamelCase):
    port_keys: list[ServicePortKey] = []


class NodeRetrieved(RetrieveDataOut):
    model_config = OutputSchema.model_config
