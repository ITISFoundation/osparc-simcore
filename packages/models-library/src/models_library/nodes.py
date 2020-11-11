from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import AnyUrl, BaseModel, Extra, Field, HttpUrl, constr, validator

from .services import KEY_RE, PROPERTY_KEY_RE, VERSION_RE

NodeID = UUID


class RunningState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PUBLISHED = "PUBLISHED"
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    STARTED = "STARTED"
    RETRY = "RETRY"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class Position(BaseModel):
    x: int = Field(..., description="The x position", example=["12"])
    y: int = Field(..., description="The y position", example=["15"])

    class Config:
        extra = Extra.forbid


class AccessEnum(str, Enum):
    ReadAndWrite = "ReadAndWrite"
    Invisible = "Invisible"
    ReadOnly = "ReadOnly"

    class Config:
        extra = Extra.forbid


class PortLink(BaseModel):
    nodeUuid: NodeID = Field(
        ...,
        description="The node to get the port output from",
        example=["da5068e0-8a8d-4fb9-9516-56e5ddaef15b"],
    )
    output: str = Field(
        ...,
        description="The port key in the node given by nodeUuid",
        regex=PROPERTY_KEY_RE,
        example=["out_2"],
    )

    class Config:
        extra = Extra.forbid


class DownloadLink(BaseModel):
    download_link: AnyUrl = Field(...)
    label: Optional[str]

    class Config:
        extra = Extra.forbid


class BaseFileLink(BaseModel):
    store: Union[str, int] = Field(
        ...,
        description="The store identifier, '0' or 0 for simcore S3, '1' or 1 for datcore",
        example=["0", 1],
    )
    path: str = Field(
        ...,
        description="The path to the file in the storage provider domain",
        example=[
            "N:package:b05739ef-260c-4038-b47d-0240d04b0599",
            "94453a6a-c8d4-52b3-a22d-ccbf81f8d636/d4442ca4-23fd-5b6b-ba6d-0b75f711c109/y_1D.txt",
        ],
    )

    class Config:
        extra = Extra.forbid


class SimCoreFileLink(BaseFileLink):
    pass


class DatCoreFileLink(BaseFileLink):
    dataset: str = Field(
        ...,
        description="Unique identifier to access the dataset on datcore (REQUIRED for datcore)",
        example=["N:dataset:f9f5ac51-33ea-4861-8e08-5b4faf655041"],
    )
    label: str = Field(
        ...,
        description="The real file name (REQUIRED for datcore)",
        example=["MyFile.txt"],
    )

    class Config:
        extra = Extra.forbid


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

    inputs: Optional[Inputs] = Field(
        default_factory=dict, description="values of input properties"
    )
    inputAccess: Optional[Dict[InputID, AccessEnum]] = Field(
        None, description="map with key - access level pairs"
    )
    inputNodes: Optional[List[NodeID]] = Field(
        default_factory=list,
        description="node IDs of where the node is connected to",
        example=["nodeUuid1", "nodeUuid2"],
    )

    outputs: Optional[Outputs] = Field({}, description="values of output properties")
    outputNode: Optional[bool] = Field(None, deprecated=True)
    outputNodes: Optional[List[NodeID]] = Field(
        None,
        description="Used in group-nodes. Node IDs of those connected to the output",
        example=["nodeUuid1", "nodeUuid2"],
    )

    parent: Optional[NodeID] = Field(
        None,
        description="Parent's (group-nodes') node ID s.",
        example=["nodeUUid1", "nodeUuid2"],
    )

    position: Optional[Position] = Field(None, deprecated=True)

    state: Optional[RunningState] = Field(
        RunningState.NOT_STARTED,
        description="the node's running state",
        example=["RUNNING", "FAILED"],
    )

    @validator("thumbnail", pre=True)
    @classmethod
    def convert_empty_str_to_none(v):
        if isinstance(v, str) and v == "":
            return None
        return v

    class Config:
        extra = Extra.forbid
