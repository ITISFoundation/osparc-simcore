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
from pydantic.config import JsonDict

from .basic_types import EnvVarKey, KeyIDStr
from .projects_access import AccessEnum
from .projects_nodes_io import (
    DatCoreFileLink,
    DownloadLink,
    NodeID,
    PortLink,
    SimCoreFileLink,
)
from .projects_nodes_layout import Position
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
    modified: Annotated[
        bool,
        Field(
            description="true if the node's outputs need to be re-computed",
        ),
    ] = True

    dependencies: Annotated[
        set[NodeID],
        Field(
            default_factory=set,
            description="contains the node inputs dependencies if they need to be computed first",
        ),
    ] = DEFAULT_FACTORY

    current_status: Annotated[
        RunningState,
        Field(
            description="the node's current state",
            alias="currentStatus",
        ),
    ] = RunningState.NOT_STARTED

    progress: Annotated[
        float | None,
        Field(
            ge=0.0,
            le=1.0,
            description="current progress of the task if available (None if not started or not a computational task)",
        ),
    ] = 0

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
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


def _convert_old_enum_name(v) -> RunningState:
    if v == "FAILURE":
        return RunningState.FAILED
    return RunningState(v)


class Node(BaseModel):
    key: Annotated[
        ServiceKey,
        Field(
            description="distinctive name for the node based on the docker registry path",
            examples=[
                "simcore/services/comp/itis/sleeper",
                "simcore/services/dynamic/3dviewer",
                "simcore/services/frontend/file-picker",
            ],
        ),
    ]
    version: Annotated[
        ServiceVersion,
        Field(
            description="semantic version number of the node",
            examples=["1.0.0", "0.0.1"],
        ),
    ]
    label: Annotated[
        str,
        Field(description="The short name of the node", examples=["JupyterLab"]),
    ]
    progress: Annotated[
        float | None,
        Field(
            ge=0,
            le=100,
            description="the node progress value (deprecated in DB, still used for API only)",
            deprecated=True,  # <-- I think this is not true, it is still used by the File Picker (frontend node)
        ),
    ] = None

    thumbnail: Annotated[  # <-- (DEPRECATED) Can be removed
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

    output_node: Annotated[bool | None, Field(deprecated=True, alias="outputNode")] = (
        None  # <-- (DEPRECATED) Can be removed
    )

    output_nodes: Annotated[  # <-- (DEPRECATED) Can be removed
        list[NodeID] | None,
        Field(
            description="Used in group-nodes. Node IDs of those connected to the output",
            alias="outputNodes",
        ),
    ] = None

    parent: Annotated[  # <-- (DEPRECATED) Can be removed
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

    @field_validator("state", mode="before")
    @classmethod
    def _convert_from_enum(cls, v):
        if isinstance(v, str):

            # the old version of state was a enum of RunningState
            running_state_value = _convert_old_enum_name(v)
            return NodeState(current_status=running_state_value)
        return v

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    # Minimal example with only required fields
                    {
                        "key": "simcore/services/comp/no_ports",
                        "version": "1.0.0",
                        "label": "Sleep",
                    },
                    # Complete example with optional fields
                    {
                        "key": "simcore/services/comp/only_inputs",
                        "version": "1.0.0",
                        "label": "Only INputs",
                        "inputs": {
                            "input_1": 1,
                            "input_2": 2,
                            "input_3": 3,
                        },
                    },
                    # Complete example with optional fields
                    {
                        "key": "simcore/services/comp/only_outputs",
                        "version": "1.0.0",
                        "label": "Only Outputs",
                        "outputs": {
                            "output_1": 1,
                            "output_2": 2,
                            "output_3": 3,
                        },
                    },
                    # Example with all possible input and output types
                    {
                        "key": "simcore/services/comp/itis/all-types",
                        "version": "1.0.0",
                        "label": "All Types Demo",
                        "inputs": {
                            "boolean_input": True,
                            "integer_input": 42,
                            "float_input": 3.14159,
                            "string_input": "text value",
                            "json_input": {"key": "value", "nested": {"data": 123}},
                            "port_link_input": {
                                "nodeUuid": "f2700a54-adcf-45d4-9881-01ec30fd75a2",
                                "output": "out_1",
                            },
                            "simcore_file_link": {
                                "store": "simcore.s3",
                                "path": "123e4567-e89b-12d3-a456-426614174000/test.csv",
                            },
                            "datcore_file_link": {
                                "store": "datcore",
                                "dataset": "N:dataset:123",
                                "path": "path/to/file.txt",
                            },
                            "download_link": {
                                "downloadLink": "https://example.com/downloadable/file.txt"
                            },
                            "array_input": [1, 2, 3, 4, 5],
                            "object_input": {"name": "test", "value": 42},
                        },
                        "outputs": {
                            "boolean_output": False,
                            "integer_output": 100,
                            "float_output": 2.71828,
                            "string_output": "result text",
                            "json_output": {"status": "success", "data": [1, 2, 3]},
                            "simcore_file_output": {
                                "store": "simcore.s3",
                                "path": "987e6543-e21b-12d3-a456-426614174000/result.csv",
                            },
                            "datcore_file_output": {
                                "store": "datcore",
                                "dataset": "N:dataset:456",
                                "path": "results/output.txt",
                            },
                            "download_link_output": {
                                "downloadLink": "https://example.com/results/download.txt"
                            },
                            "array_output": ["a", "b", "c", "d"],
                            "object_output": {"status": "complete", "count": 42},
                        },
                    },
                ],
            }
        )

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        json_schema_extra=_update_json_schema_extra,
    )


class PartialNode(Node):
    key: Annotated[ServiceKey, Field(default=None)]
    version: Annotated[ServiceVersion, Field(default=None)]
    label: Annotated[str, Field(default=None)]
