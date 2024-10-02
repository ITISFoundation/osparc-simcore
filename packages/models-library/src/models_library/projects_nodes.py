"""
    Models Node as a central element in a project's pipeline
"""

from copy import deepcopy
from typing import Annotated, Any, TypeAlias, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    Json,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    field_validator,
)

from .basic_types import EnvVarKey, KeyIDStr
from .projects_access import AccessEnum
from .projects_nodes_io import (
    DatCoreFileLink,
    DownloadLink,
    NodeID,
    PortLink,
    SimCoreFileLink,
)
from .projects_nodes_ui import Position
from .projects_state import RunningState
from .services import ServiceKey, ServiceVersion

InputTypes = Union[
    # NOTE: WARNING the order in Union[*] below matters!
    StrictBool,
    StrictInt,
    StrictFloat,
    Json,
    str,
    PortLink,
    SimCoreFileLink | DatCoreFileLink,  # *FileLink to service
    DownloadLink,
    list[Any] | dict[str, Any],  # arrays | object
]
OutputTypes = Union[
    # NOTE: WARNING the order in Union[*] below matters!
    StrictBool,
    StrictInt,
    StrictFloat,
    Json,
    str,
    SimCoreFileLink | DatCoreFileLink,  # *FileLink to service
    DownloadLink,
    list[Any] | dict[str, Any],  # arrays | object
]


InputID: TypeAlias = KeyIDStr
OutputID: TypeAlias = KeyIDStr

# union_mode="smart" by default for Pydantic>=2: https://docs.pydantic.dev/latest/concepts/unions/#union-modes
InputsDict: TypeAlias = dict[
    InputID, Annotated[InputTypes, Field(union_mode="left_to_right")]
]
OutputsDict: TypeAlias = dict[
    OutputID, Annotated[OutputTypes, Field(union_mode="left_to_right")]
]

UnitStr: TypeAlias = Annotated[str, StringConstraints(strip_whitespace=True)]


class NodeState(BaseModel):
    modified: bool = Field(
        default=True, description="true if the node's outputs need to be re-computed"
    )
    dependencies: set[NodeID] = Field(
        default_factory=set,
        description="contains the node inputs dependencies if they need to be computed first",
    )
    current_status: RunningState = Field(
        default=RunningState.NOT_STARTED,
        description="the node's current state",
        alias="currentStatus",
    )
    progress: float | None = Field(
        default=0,
        ge=0.0,
        le=1.0,
        description="current progress of the task if available (None if not started or not a computational task)",
    )
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "modified": True,
                    "dependencies": [],
                    "currentStatus": "NOT_STARTED",
                },
                {
                    "modified": True,
                    "dependencies": ["42838344-03de-4ce2-8d93-589a5dcdfd05"],
                    "currentStatus": "ABORTED",
                },
                {
                    "modified": False,
                    "dependencies": [],
                    "currentStatus": "SUCCESS",
                },
            ]
        },
    )


def _patch_json_schema_extra(schema: dict) -> None:
    # NOTE: exporting without this trick does not make runHash as nullable.
    # It is a Pydantic issue see https://github.com/samuelcolvin/pydantic/issues/1270
    for prop_name in ["parent", "runHash"]:
        if prop_name in schema.get("properties", {}):
            prop = deepcopy(schema["properties"][prop_name])
            prop["nullable"] = True
            schema["properties"][prop_name] = prop


class Node(BaseModel):
    key: ServiceKey = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        examples=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
            "simcore/services/frontend/file-picker",
        ],
    )
    version: ServiceVersion = Field(
        ...,
        description="semantic version number of the node",
        examples=["1.0.0", "0.0.1"],
    )
    label: str = Field(
        ..., description="The short name of the node", examples=["JupyterLab"]
    )
    progress: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="the node progress value (deprecated in DB, still used for API only)",
        deprecated=True,
    )
    thumbnail: Annotated[str, HttpUrl] | None = Field(
        default=None,
        description="url of the latest screenshot of the node",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )

    # RUN HASH
    run_hash: str | None = Field(
        default=None,
        description="the hex digest of the resolved inputs +outputs hash at the time when the last outputs were generated",
        alias="runHash",
    )

    # INPUT PORTS ---
    inputs: InputsDict | None = Field(
        default_factory=dict, description="values of input properties"
    )
    inputs_required: list[InputID] = Field(
        default_factory=list,
        description="Defines inputs that are required in order to run the service",
        alias="inputsRequired",
    )
    inputs_units: dict[InputID, UnitStr] | None = Field(
        default=None,
        description="Overrides default unit (if any) defined in the service for each port",
        alias="inputsUnits",
    )
    input_access: dict[InputID, AccessEnum] | None = Field(
        default=None,
        description="map with key - access level pairs",
        alias="inputAccess",
    )
    input_nodes: list[NodeID] | None = Field(
        default_factory=list,
        description="node IDs of where the node is connected to",
        alias="inputNodes",
    )

    # OUTPUT PORTS ---
    outputs: OutputsDict | None = Field(
        default_factory=dict, description="values of output properties"
    )
    output_node: bool | None = Field(default=None, deprecated=True, alias="outputNode")
    output_nodes: list[NodeID] | None = Field(
        default=None,
        description="Used in group-nodes. Node IDs of those connected to the output",
        alias="outputNodes",
    )

    parent: NodeID | None = Field(
        default=None,
        description="Parent's (group-nodes') node ID s. Used to group",
    )

    position: Position | None = Field(
        default=None,
        deprecated=True,
        description="Use projects_ui.WorkbenchUI.position instead",
    )

    state: NodeState | None = Field(
        default_factory=NodeState, description="The node's state object"
    )

    boot_options: dict[EnvVarKey, str] | None = Field(
        default=None,
        alias="bootOptions",
        description=(
            "Some services provide alternative parameters to be injected at boot time. "
            "The user selection should be stored here, and it will overwrite the "
            "services's defaults."
        ),
    )

    @field_validator("thumbnail", mode="before")
    @classmethod
    def convert_empty_str_to_none(cls, v):
        if isinstance(v, str) and v == "":
            return None
        return v

    @classmethod
    def convert_old_enum_name(cls, v) -> RunningState:
        if v == "FAILURE":
            return RunningState.FAILED
        return RunningState(v)

    @field_validator("state", mode="before")
    @classmethod
    def convert_from_enum(cls, v):
        if isinstance(v, str):
            # the old version of state was a enum of RunningState
            running_state_value = cls.convert_old_enum_name(v)
            return NodeState(currentStatus=running_state_value)
        return v

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra=_patch_json_schema_extra,
    )
