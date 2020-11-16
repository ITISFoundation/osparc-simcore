import sys
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Extra, Field, HttpUrl, PositiveInt, constr

from .project_nodes import Node, NodeID, Position, RunningState

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()

DATE_RE = r"\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\d)T(2[0-3]|1\d|0?[0-9])(:(\d|[0-5]\d)){2}(\.\d{3})?Z"

GroupID = constr(regex=r"^\S+$")

# Pydantic does not support exporting a jsonschema with Dict keys being something else than a str
# this is a regex for having uuids of type: 8-4-4-4-12 digits
_NodeID_For_Dict = constr(
    regex=r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
)
ProjectID = UUID
ClassifierID = str
Workbench = Dict[_NodeID_For_Dict, Node]


class WorkbenchUI(BaseModel):
    position: Position = Field(..., description="The node position in the workbench")

    class Config:
        extra = Extra.forbid


class Slideshow(BaseModel):
    position: int = Field(..., description="Slide's position", example=["0", "2"])

    class Config:
        extra = Extra.forbid


class StudyUI(BaseModel):
    workbench: Optional[Dict[_NodeID_For_Dict, WorkbenchUI]] = Field(None)
    slideshow: Optional[Dict[_NodeID_For_Dict, Slideshow]] = Field(None)
    current_node_id: Optional[NodeID] = Field(alias="currentNodeId")

    class Config:
        extra = Extra.allow


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

    class Config:
        extra = Extra.forbid


class ProjectLocked(BaseModel):
    value: bool = Field(
        ..., description="True if the project is locked by another user"
    )
    owner: Optional[Owner] = Field(None, description="The user that owns the lock")

    class Config:
        extra = Extra.forbid


class ProjectRunningState(BaseModel):
    value: RunningState = Field(
        ..., description="The running state of the project", example=["STARTED"]
    )

    class Config:
        extra = Extra.forbid


class ProjectState(BaseModel):
    locked: ProjectLocked = Field(..., description="The project lock state")
    state: ProjectRunningState = Field(..., description="The project running state")

    class Config:
        extra = Extra.forbid


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
