"""
    Models a study's project document
"""
from copy import deepcopy
from typing import Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, Extra, Field, HttpUrl, validator

from .basic_regex import DATE_RE
from .projects_access import AccessRights, GroupID
from .projects_nodes import Node
from .projects_nodes_io import NodeID_AsDictKey
from .projects_state import ProjectState
from .projects_ui import StudyUI

ProjectID = UUID
ClassifierID = str

# TODO: for some reason class Workbench(BaseModel): __root__= does not work as I thought ... investigate!
Workbench = Dict[NodeID_AsDictKey, Node]


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
    thumbnail: Union[str, HttpUrl] = Field(
        ...,
        description="url of the project thumbnail",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )

    # Ownership and Access  (SEE projects_access.py)
    prjOwner: EmailStr = Field(..., description="user email")
    accessRights: Dict[GroupID, AccessRights] = Field(
        ...,
        description="object containing the GroupID as key and read/write/execution permissions as value",
    )

    # Timestamps   TODO: should we use datetime??
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
        default_factory=list,
        description="Contains the reference to the project classifiers",
        examples=["some:id:to:a:classifier"],
    )

    # Pipeline of nodes ( SEE projects_nodes.py)
    workbench: Workbench = ...

    # Project state (SEE projects_state.py)
    state: Optional[ProjectState] = None

    # UI front-end setup (SEE projects_ui.py)
    ui: Optional[StudyUI] = None

    # Dev only
    dev: Optional[Dict] = Field(description="object used for development purposes only")

    @classmethod
    @validator("thumbnail")
    def null_thumbnail(cls, v):
        if isinstance(v, str) and v == "":
            return None
        return v

    class Config:
        description = "Document that stores metadata, pipeline and UI setup of a study"
        title = "osparc-simcore project"
        extra = Extra.forbid

        # pylint: disable=no-self-argument
        def schema_extra(schema: Dict, _model: "Project"):
            # pylint: disable=unsubscriptable-object

            # Patch to allow jsonschema nullable
            # SEE https://github.com/samuelcolvin/pydantic/issues/990#issuecomment-645961530
            state_pydantic_schema = deepcopy(schema["properties"]["state"])
            schema["properties"]["state"] = {
                "anyOf": [{"type": "null"}, state_pydantic_schema]
            }
