import sys
from copy import deepcopy
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, Extra, Field, HttpUrl, constr

from .basic_regex import DATE_RE, UUID_RE
from .project_nodes import Node, NodeID
from .projects_state import ProjectState
from .projects_ui import StudyUI

#
#
#
# NOTE: "examples" = [ ...] keyword and NOT "example". See https://json-schema.org/understanding-json-schema/reference/generic.html#annotations
#

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()


GroupID = constr(regex=r"^\S+$")
ProjectID = UUID

GroupID = constr(regex=r"^\d+$")
NodeID = constr(regex=UUID_RE)
ClassifierID = str


class AccessEnum(str, Enum):
    ReadAndWrite = "ReadAndWrite"
    Invisible = "Invisible"
    ReadOnly = "ReadOnly"


class AccessRights(BaseModel):
    read: bool = Field(..., description="gives read access")
    write: bool = Field(..., description="gives write access")
    delete: bool = Field(..., description="gives deletion rights")

    class Config:
        extra = Extra.forbid


class Project(BaseModel):
    uuid: ProjectID = Field(
        ...,
        description="project unique identifier",
        examples=[
            "07640335-a91f-468c-ab69-a374fa82078d",
            "9bcf8feb-c1b1-41b6-b201-639cd6ccdba8",
        ],
    )

    # Description of the project
    name: str = Field(
        ..., description="project name", examples=["Temporal Distortion Simulator"]
    )
    description: str = Field(
        ...,
        description="longer one-line description about the project",
        examples=["Dabbling in temporal transitions ..."],
    )
    thumbnail: HttpUrl = Field(
        ...,
        description="url of the project thumbnail",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )

    # Ownership and access
    prjOwner: EmailStr = Field(..., description="user email")
    accessRights: Dict[GroupID, AccessRights] = Field(
        ...,
        description="object containing the GroupID as key and read/write/execution permissions as value",
    )

    # Timestamps
    creationDate: str = Field(
        ...,
        regex=DATE_RE,
        description="project creation date",
        examples=["2018-07-01T11:13:43Z"],
    )
    lastChangeDate: str = Field(
        ...,
        regex=DATE_RE,
        description="last save date",
        examples=["2018-07-01T11:13:43Z"],
    )

    # Classification
    tags: Optional[List[int]] = []
    classifiers: Optional[List[ClassifierID]] = Field(
        [],
        description="Contains the reference to the project classifiers",
        examples=["some:id:to:a:classifier"],
    )

    # Pipeline
    workbench: Dict[NodeID, Node] = ...

    # Front-end specific
    ui: Union[StudyUI, None] = None
    dev: Dict = Field({}, description="object used for development purpoqses only")

    # State
    state: Optional[ProjectState] = None

    class Config:
        description = "Description of a simcore project"
        title = "simcore project"
        extra = Extra.forbid

        # pylint: disable=no-self-argument
        def schema_extra(schema: Dict, _model: "Project"):
            # pylint: disable=unsubscriptable-object

            # Patch to allow 'state' to be nullable
            #  See https://github.com/samuelcolvin/pydantic/issues/990#issuecomment-645961530
            state_pydantic_schema = deepcopy(schema["properties"]["state"])
            schema["properties"]["state"].update(
                {"anyOf": [{"type": "null"}, state_pydantic_schema]}
            )
