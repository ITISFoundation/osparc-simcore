"""
    DB models in sqlalchemy
    API schemas and domain models in pydantic
"""

import sys
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, EmailStr, Field, constr

from simcore_postgres_database.webserver_models import ProjectType, projects

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()

KEY_RE = r"^(simcore)/(services)(/demodec)?/(comp|dynamic|frontend)(/[^\s]+)+$"
VERSION_RE = r"^(0|[1-9]\d*)(\.(0|[1-9]\d*)){2}(-(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*)(\.(0|[1-9]\d*|\d*[-a-zA-Z][-\da-zA-Z]*))*)?(\+[-\da-zA-Z]+(\.[-\da-zA-Z-]+)*)?$"
DATE_RE = r"\\d{4}-(12|11|10|0?[1-9])-(31|30|[0-2]?\\d)T(2[0-3]|1\\d|0?[0-9])(:(\\d|[0-5]\\d)){2}(\\.\\d{3})?Z"


__all__ = [
    "projects",
    "ProjectType",
    "ProjectState",
    "ProjectLocked",
    "Owner",
]


class Connection(BaseModel):
    nodeUuid: Optional[str]
    output: Optional[str]


class FilePickerOutput(BaseModel):
    store: Union[str, int]  # simcore/datcore
    dataset: Optional[str]
    path: str
    label: str  # name of the file


class AccessEnum(str, Enum):
    ReadAndWrite = "ReadAndWrite"
    Invisible = "Invisible"
    ReadOnly = "ReadOnly"


class Position(BaseModel):
    x: int
    y: int


InputTypes = Union[int, bool, str, float, Connection, FilePickerOutput]
OutputTypes = Union[int, bool, str, float, FilePickerOutput]
InputID = constr(regex=r"^[-_a-zA-Z0-9]+$")
OutputID = InputID


class Node(BaseModel):
    key: str = Field(..., regex=KEY_RE, example="simcore/services/comp/sleeper")
    version: str = Field(..., regex=VERSION_RE, example="6.2.0")
    label: str = Field(...)
    progress: float = Field(0, ge=0, le=100)
    thumbnail: Optional[str]

    inputs: Optional[Dict[InputID, InputTypes]]
    inputAccess: Optional[Dict[InputID, AccessEnum]]
    inputNodes: List[str] = []

    outputs: Optional[Dict[OutputID, OutputTypes]] = None
    outputNode: Optional[bool] = Field(None, deprecated=True)
    outputNodes: List[OutputID] = Field(
        [], description="Used in group-nodes. Node IDs of those connected to the output"
    )

    parent: Optional[str] = Field(
        None, description="Parent's (group-nodes') node ID s.", example="nodeUUid1"
    )

    position: Position = Field(...)


class AccessRights(BaseModel):
    read: bool
    write: bool
    delete: bool


GroupID = constr(regex="^\\d+$")
NodeID = constr(strip_whitespace=True, min_length=1)
ClassifierID = constr(strip_whitespace=True, min_length=1)


class Project(BaseModel):
    uuid: str
    name: str
    description: str
    prjOwner: EmailStr
    accessRights: Dict[GroupID, AccessRights] = Field(
        ...,
        description="object containing the GroupID as key and read/write/execution permissions as value",
    )
    creationDate: str = Field(..., regex=DATE_RE)
    lastChangeDate: str = Field(..., regex=DATE_RE)
    thumbnail: str
    workbench: Dict[NodeID, Node]
    tags: Optional[List[int]] = []
    classifiers: Optional[List[ClassifierID]] = Field(
        [],
        description="Contains the reference to the project classifiers",
        example=["some:id:to:a:classifier"],
    )
    dev: Optional[Dict[str, str]] = Field(
        {}, description="object used for development purposes only"
    )


class Owner(BaseModel):
    first_name: str
    last_name: str


class ProjectLocked(BaseModel):
    value: bool
    owner: Optional[Owner]


class ProjectState(BaseModel):
    locked: ProjectLocked


# API schemas
class ProjectIn(Project):
    pass


class ProjectOut(Project):
    # allOf = [Project, ProjectState]
    state: Optional[ProjectState]


if __name__ == "__main__":

    with open(current_file.with_suffix(".json"), "wt") as fh:
        print(ProjectOut.schema_json(indent=2), file=fh)
