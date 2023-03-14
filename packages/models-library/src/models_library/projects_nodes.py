"""
    Models Node as a central element in a project's pipeline
"""

from copy import deepcopy
from typing import Any, Optional, Union

from pydantic import (
    BaseModel,
    Extra,
    Field,
    Json,
    StrictBool,
    StrictFloat,
    StrictInt,
    constr,
    validator,
)

from .basic_regex import VERSION_RE
from .basic_types import EnvVarKey
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
from .services import PROPERTY_KEY_RE, SERVICE_KEY_RE

# NOTE: WARNING the order here matters

InputTypes = Union[
    StrictBool,
    StrictInt,
    StrictFloat,
    Json,  # FIXME: remove if OM sends object/array. create project does NOT use pydantic
    str,
    PortLink,
    Union[SimCoreFileLink, DatCoreFileLink],  # *FileLink to service
    DownloadLink,
    Union[list[Any], dict[str, Any]],  # arrays | object
]
OutputTypes = Union[
    StrictBool,
    StrictInt,
    StrictFloat,
    Json,  # TODO: remove when OM sends object/array instead of json-formatted strings
    str,
    Union[SimCoreFileLink, DatCoreFileLink],  # *FileLink to service
    DownloadLink,
    Union[list[Any], dict[str, Any]],  # arrays | object
]

InputID = OutputID = constr(regex=PROPERTY_KEY_RE)
InputsDict = dict[InputID, InputTypes]
OutputsDict = dict[OutputID, OutputTypes]
UnitStr = constr(strip_whitespace=True)


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

    class Config:
        extra = Extra.forbid
        schema_extra = {
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
        }


class Node(BaseModel):
    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=SERVICE_KEY_RE,
        examples=[
            "simcore/services/comp/itis/sleeper",
            "simcore/services/dynamic/3dviewer",
            "simcore/services/frontend/file-picker",
        ],
    )
    version: str = Field(
        ...,
        description="semantic version number of the node",
        regex=VERSION_RE,
        examples=["1.0.0", "0.0.1"],
    )
    label: str = Field(
        ..., description="The short name of the node", examples=["JupyterLab"]
    )
    progress: Optional[float] = Field(
        None, ge=0, le=100, description="the node progress value"
    )
    thumbnail: Optional[str] = Field(
        None,
        description="url of the latest screenshot of the node",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
        min_length=0,
        max_length=2083,
        format="uri",
    )

    # RUN HASH
    run_hash: Optional[str] = Field(
        None,
        description="the hex digest of the resolved inputs +outputs hash at the time when the last outputs were generated",
        alias="runHash",
    )

    # INPUT PORTS ---
    inputs: Optional[InputsDict] = Field(
        default_factory=dict, description="values of input properties"
    )
    inputs_units: Optional[dict[InputID, UnitStr]] = Field(
        None,
        description="Overrides default unit (if any) defined in the service for each port",
        alias="inputsUnits",
    )
    input_access: Optional[dict[InputID, AccessEnum]] = Field(
        None, description="map with key - access level pairs", alias="inputAccess"
    )
    input_nodes: Optional[list[NodeID]] = Field(
        default_factory=list,
        description="node IDs of where the node is connected to",
        alias="inputNodes",
    )

    # OUTPUT PORTS ---
    outputs: Optional[OutputsDict] = Field(
        default_factory=dict, description="values of output properties"
    )
    output_node: Optional[bool] = Field(None, deprecated=True, alias="outputNode")
    output_nodes: Optional[list[NodeID]] = Field(
        None,
        description="Used in group-nodes. Node IDs of those connected to the output",
        alias="outputNodes",
    )

    parent: Optional[NodeID] = Field(
        None,
        description="Parent's (group-nodes') node ID s. Used to group",
    )

    position: Optional[Position] = Field(
        None,
        deprecated=True,
        description="Use projects_ui.WorkbenchUI.position instead",
    )

    state: Optional[NodeState] = Field(
        default_factory=NodeState, description="The node's state object"
    )

    boot_options: Optional[dict[EnvVarKey, str]] = Field(
        None,
        alias="bootOptions",
        description=(
            "Some services provide alternative parameters to be injected at boot time. "
            "The user selection should be stored here, and it will overwrite the "
            "services's defaults."
        ),
    )

    @validator("thumbnail", pre=True)
    @classmethod
    def convert_empty_str_to_none(cls, v):
        if isinstance(v, str) and v == "":
            return None
        return v

    @classmethod
    def convert_old_enum_name(cls, v) -> RunningState:
        if v == "FAILURE":
            return RunningState.FAILED
        return v

    @validator("state", pre=True)
    @classmethod
    def convert_from_enum(cls, v):
        if isinstance(v, str):
            # the old version of state was a enum of RunningState
            running_state_value = cls.convert_old_enum_name(v)
            return NodeState(currentStatus=running_state_value)
        return v

    class Config:
        extra = Extra.forbid

        # NOTE: exporting without this trick does not make runHash as nullable.
        # It is a Pydantic issue see https://github.com/samuelcolvin/pydantic/issues/1270
        @staticmethod
        def schema_extra(schema, _model: "Node"):
            # NOTE: the variant with anyOf[{type: null}, { other }] is compatible with OpenAPI
            # The other as type = [null, other] is only jsonschema compatible
            for prop_name in ["parent", "runHash"]:
                if prop_name in schema.get("properties", {}):
                    was = deepcopy(schema["properties"][prop_name])
                    schema["properties"][prop_name] = {"anyOf": [{"type": "null"}, was]}
