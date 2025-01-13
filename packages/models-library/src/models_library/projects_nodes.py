"""
    Models Node as a central element in a project's pipeline
"""

from typing import Annotated, Any, TypeAlias, Union

from common_library.basic_types import DEFAULT_FACTORY
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
    progress: Annotated[
        float | None,
        Field(
            ge=0,
            le=100,
            description="the node progress value (deprecated in DB, still used for API only)",
            deprecated=True,
        ),
    ] = None

    thumbnail: Annotated[
        str | HttpUrl | None,
        Field(
            description="url of the latest screenshot of the node",
            examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
        ),
    ] = None

    # RUN HASH
    run_hash: Annotated[
        str | None,
        Field(
            description="the hex digest of the resolved inputs +outputs hash at the time when the last outputs were generated",
            alias="runHash",
        ),
    ] = None

    # INPUT PORTS ---
    inputs: Annotated[
        InputsDict | None,
        Field(default_factory=dict, description="values of input properties"),
    ] = DEFAULT_FACTORY

    inputs_required: Annotated[
        list[InputID],
        Field(
            default_factory=list,
            description="Defines inputs that are required in order to run the service",
            alias="inputsRequired",
        ),
    ] = DEFAULT_FACTORY

    inputs_units: Annotated[
        dict[InputID, UnitStr] | None,
        Field(
            description="Overrides default unit (if any) defined in the service for each port",
            alias="inputsUnits",
        ),
    ] = None

    input_access: Annotated[
        dict[InputID, AccessEnum] | None,
        Field(
            description="map with key - access level pairs",
            alias="inputAccess",
        ),
    ] = None

    input_nodes: Annotated[
        list[NodeID] | None,
        Field(
            default_factory=list,
            description="node IDs of where the node is connected to",
            alias="inputNodes",
        ),
    ] = DEFAULT_FACTORY

    # OUTPUT PORTS ---
    outputs: Annotated[
        OutputsDict | None,
        Field(default_factory=dict, description="values of output properties"),
    ] = DEFAULT_FACTORY

    output_node: Annotated[
        bool | None, Field(deprecated=True, alias="outputNode")
    ] = None

    output_nodes: Annotated[
        list[NodeID] | None,
        Field(
            description="Used in group-nodes. Node IDs of those connected to the output",
            alias="outputNodes",
        ),
    ] = None

    parent: Annotated[
        NodeID | None,
        Field(
            description="Parent's (group-nodes') node ID s. Used to group",
        ),
    ] = None

    position: Annotated[
        Position | None,
        Field(
            deprecated=True,
            description="Use projects_ui.WorkbenchUI.position instead",
        ),
    ] = None

    state: Annotated[
        NodeState | None,
        Field(default_factory=NodeState, description="The node's state object"),
    ] = DEFAULT_FACTORY

    boot_options: Annotated[
        dict[EnvVarKey, str] | None,
        Field(
            alias="bootOptions",
            description=(
                "Some services provide alternative parameters to be injected at boot time. "
                "The user selection should be stored here, and it will overwrite the "
                "services's defaults."
            ),
        ),
    ] = None

    @field_validator("thumbnail", mode="before")
    @classmethod
    def _convert_empty_str_to_none(cls, v):
        if isinstance(v, str) and v == "":
            return None
        return v

    @classmethod
    def _convert_old_enum_name(cls, v) -> RunningState:
        if v == "FAILURE":
            return RunningState.FAILED
        return RunningState(v)

    @field_validator("state", mode="before")
    @classmethod
    def _convert_from_enum(cls, v):
        if isinstance(v, str):
            # the old version of state was a enum of RunningState
            running_state_value = cls._convert_old_enum_name(v)
            return NodeState(currentStatus=running_state_value)
        return v

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )


class PartialNode(Node):
    key: Annotated[ServiceKey | None, Field(default=None)]
    version: Annotated[ServiceVersion | None, Field(default=None)]
