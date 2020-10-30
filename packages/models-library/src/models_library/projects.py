import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, Extra, Field, HttpUrl, constr, validator

from .services import KEY_RE, PROPERTY_KEY_RE, VERSION_RE

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()

DATE_RE = r"\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\d)T(2[0-3]|1\d|0?[0-9])(:(\d|[0-5]\d)){2}(\.\d{3})?Z"

GroupID = constr(regex=r"^\S+$")
NodeID = UUID
ProjectID = UUID
ClassifierID = str


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


class AccessEnum(str, Enum):
    ReadAndWrite = "ReadAndWrite"
    Invisible = "Invisible"
    ReadOnly = "ReadOnly"


class Position(BaseModel):
    x: int = Field(..., description="The x position", example=["12"])
    y: int = Field(..., description="The y position", example=["15"])

    class Config:
        extra = Extra.forbid


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")

    class Config:
        extra = Extra.forbid


class Slideshow(BaseModel):
    position: int = Field(..., description="Slide's position", example=["0", "2"])

    class Config:
        extra = Extra.forbid


InputTypes = Union[int, bool, str, float, PortLink, SimCoreFileLink, DatCoreFileLink]
OutputTypes = Union[int, bool, str, float, SimCoreFileLink, DatCoreFileLink]
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

    inputs: Optional[Inputs] = Field(None, description="values of input properties")
    inputAccess: Optional[Dict[InputID, AccessEnum]] = Field(
        None, description="map with key - access level pairs"
    )
    inputNodes: Optional[List[UUID]] = Field(
        None,
        description="node IDs of where the node is connected to",
        example=["nodeUuid1", "nodeUuid2"],
    )

    outputs: Optional[Outputs] = None
    outputNode: Optional[bool] = Field(None, deprecated=True)
    outputNodes: Optional[List[UUID]] = Field(
        None,
        description="Used in group-nodes. Node IDs of those connected to the output",
        example=["nodeUuid1", "nodeUuid2"],
    )

    parent: Optional[UUID] = Field(
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


class StudyUI(BaseModel):
    workbench: Optional[Dict[NodeID, WorkbenchUI]] = Field(None)
    slideshow: Optional[Dict[NodeID, Slideshow]] = Field(None)


class AccessRights(BaseModel):
    read: bool = Field(..., description="gives read access")
    write: bool = Field(..., description="gives write access")
    delete: bool = Field(..., description="gives deletion rights")

    class Config:
        extra = Extra.forbid


class Owner(BaseModel):
    user_id: PositiveInt = Field(
        ...,
        description="Owner's identifier when registered in the user's database table",
        example=[2],
    )
    first_name: str = Field(..., description="Owner first name", example=["John"])
    last_name: str = Field(..., description="Owner last name", example=["Smith"])


class ProjectLocked(BaseModel):
    value: bool = Field(
        ..., description="True if the project is locked by another user"
    )
    owner: Optional[Owner] = Field(None, description="The user that owns the lock")


class ProjectRunningState(BaseModel):
    value: RunningState = Field(
        ..., description="The running state of the project", example=["STARTED"]
    )


class ProjectState(BaseModel):
    locked: ProjectLocked = Field(..., description="The project lock state")
    state: ProjectRunningState = Field(..., description="The project running state")


Workbench = Dict[NodeID, Node]


class Project(BaseModel):
    uuid: ProjectID = Field(
        ...,
        description="project unique identifier",
        example=[
            "07640335-a91f-468c-ab69-a374fa82078d",
            "9bcf8feb-c1b1-41b6-b201-639cd6ccdba8",
        ],
    )
    name: str = Field(
        ..., description="project name", example=["Temporal Distortion Simulator"]
    )
    description: str = Field(
        ...,
        description="longer one-line description about the project",
        example=["Dabbling in temporal transitions ..."],
    )
    prjOwner: EmailStr = Field(..., description="user email")
    accessRights: Dict[GroupID, AccessRights] = Field(
        ...,
        description="object containing the GroupID as key and read/write/execution permissions as value",
        additionalProperties=False,
    )
    creationDate: str = Field(
        ...,
        regex=DATE_RE,
        description="project creation date",
        example=["2018-07-01T11:13:43Z"],
    )
    lastChangeDate: str = Field(
        ...,
        regex=DATE_RE,
        description="last save date",
        example=["2018-07-01T11:13:43Z"],
    )
    thumbnail: HttpUrl = Field(
        ...,
        description="url of the project thumbnail",
        example=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )
    workbench: Workbench
    ui: Optional[StudyUI]
    tags: Optional[List[int]] = Field(None)
    classifiers: Optional[List[ClassifierID]] = Field(
        None,
        description="Contains the reference to the project classifiers",
        example=["some:id:to:a:classifier"],
    )
    dev: Optional[Dict] = Field(
        None, description="object used for development purposes only"
    )
    state: Optional[ProjectState] = Field(None, description="Project state")

    class Config:
        description = "Description of a simcore project"
        title = "simcore project"
        extra = Extra.forbid
