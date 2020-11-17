"""
    Models Node as a central element in a project's pipeline
"""

from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Extra, Field, HttpUrl, constr, validator

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
from .services import KEY_RE, PROPERTY_KEY_RE, VERSION_RE

InputTypes = Union[
    int, bool, str, float, PortLink, SimCoreFileLink, DatCoreFileLink, DownloadLink
]
OutputTypes = Union[
    int, bool, str, float, SimCoreFileLink, DatCoreFileLink, DownloadLink
]

InputID = constr(regex=PROPERTY_KEY_RE)
OutputID = InputID
Inputs = Dict[InputID, InputTypes]
Outputs = Dict[OutputID, OutputTypes]


class Node(BaseModel):
    key: str = Field(
        ...,
        description="distinctive name for the node based on the docker registry path",
        regex=KEY_RE,
        example=[
            "simcore/services/comp/sleeper",
            "simcore/services/dynamic/3dviewer",
            "simcore/services/frontend/file-picker",
        ],
    )
    version: str = Field(
        ...,
        description="semantic version number of the node",
        regex=VERSION_RE,
        example=["1.0.0", "0.0.1"],
    )
    label: str = Field(
        ..., description="The short name of the node", example=["JupyterLab"]
    )
    progress: Optional[float] = Field(
        None, ge=0, le=100, description="the node progress value"
    )
    thumbnail: Optional[HttpUrl] = Field(
        None,
        description="url of the latest screenshot of the node",
        example=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )

    # INPUT PORTS ---

    inputs: Optional[Inputs] = Field(
        default_factory=dict, description="values of input properties"
    )
    input_access: Optional[Dict[InputID, AccessEnum]] = Field(
        None, description="map with key - access level pairs", alias="inputAccess"
    )
    input_nodes: Optional[List[NodeID]] = Field(
        default_factory=list,
        description="node IDs of where the node is connected to",
        example=["nodeUuid1", "nodeUuid2"],
        alias="inputNodes",
    )

    # OUTPUT PORTS ---
    outputs: Optional[Outputs] = Field(
        default_factory=dict, description="values of output properties"
    )
    output_node: Optional[bool] = Field(None, deprecated=True, alias="outputNode")
    output_nodes: Optional[List[NodeID]] = Field(
        None,
        description="Used in group-nodes. Node IDs of those connected to the output",
        example=["nodeUuid1", "nodeUuid2"],
        alias="outputNodes",
    )

    parent: Optional[NodeID] = Field(
        None,
        description="Parent's (group-nodes') node ID s. Used to group",
        example=["nodeUUid1", "nodeUuid2"],
    )

    state: Optional[RunningState] = Field(
        RunningState.NOT_STARTED,
        description="the node's running state",
        example=["RUNNING", "FAILED"],
    )

    # NOTE: use projects_ui.py
    position: Optional[Position] = Field(None, deprecated=True)

    @validator("thumbnail", pre=True)
    @classmethod
    def convert_empty_str_to_none(v):
        if isinstance(v, str) and v == "":
            return None
        return v

    @validator("state", pre=True)
    @classmethod
    def convert_old_enum_name(v):
        if v == "FAILURE":
            return RunningState.FAILED
        return v

    class Config:
        extra = Extra.forbid
