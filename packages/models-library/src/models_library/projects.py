"""
    Models a study's project document
"""
from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Extra, Field, HttpUrl, constr, validator

from .basic_regex import DATE_RE, UUID_RE
from .projects_access import AccessRights, GroupID
from .projects_nodes import Node
from .projects_nodes_io import NodeIDStr
from .projects_state import ProjectState
from .projects_ui import StudyUI

ProjectID = UUID
ProjectIDStr = constr(regex=UUID_RE)

ClassifierID = str

# TODO: for some reason class Workbench(BaseModel): __root__= does not work as I thought ... investigate!
Workbench = Dict[NodeIDStr, Node]


# NOTE: careful this is in sync with packages/postgres-database/src/simcore_postgres_database/models/projects.py!!!
class ProjectType(str, Enum):
    """
    template: template project
    standard: standard project
    """

    TEMPLATE = "TEMPLATE"
    STANDARD = "STANDARD"


class ProjectCommons(BaseModel):
    # Description of the project
    uuid: ProjectID = Field(
        ...,
        description="project unique identifier",
        examples=[
            "07640335-a91f-468c-ab69-a374fa82078d",
            "9bcf8feb-c1b1-41b6-b201-639cd6ccdba8",
        ],
    )
    name: str = Field(
        ..., description="project name", examples=["Temporal Distortion Simulator"]
    )
    description: str = Field(
        ...,
        description="longer one-line description about the project",
        examples=["Dabbling in temporal transitions ..."],
    )
    thumbnail: Optional[HttpUrl] = Field(
        ...,
        description="url of the project thumbnail",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )

    creation_date: datetime = Field(...)
    last_change_date: datetime = Field(...)

    # Pipeline of nodes (SEE projects_nodes.py)
    workbench: Workbench = Field(..., description="Project's pipeline")

    @validator("thumbnail", always=True, pre=True)
    @classmethod
    def convert_empty_str_to_none(cls, v):
        if isinstance(v, str) and v == "":
            return None
        return v


class ProjectAtDB(ProjectCommons):
    # Model used to READ from database

    id: int = Field(..., description="The table primary index")

    project_type: ProjectType = Field(..., alias="type", description="The project type")

    prj_owner: Optional[int] = Field(..., description="The project owner id")

    published: Optional[bool] = Field(
        False, description="Defines if a study is available publicly"
    )

    @validator("project_type", pre=True)
    @classmethod
    def convert_sql_alchemy_enum(cls, v):
        if isinstance(v, Enum):
            return v.value
        return v

    class Config:
        orm_mode = True
        use_enum_values = True


class Project(ProjectCommons):
    # NOTE: This is the pydantic pendant of project-v0.0.1.json used in the API of the webserver/webclient
    # NOT for usage with DB!!

    # Ownership and Access  (SEE projects_access.py)
    prj_owner: EmailStr = Field(..., description="user email", alias="prjOwner")

    # Timestamps   TODO: should we use datetime??
    creation_date: str = Field(
        ...,
        regex=DATE_RE,
        description="project creation date",
        examples=["2018-07-01T11:13:43Z"],
        alias="creationDate",
    )
    last_change_date: str = Field(
        ...,
        regex=DATE_RE,
        description="last save date",
        examples=["2018-07-01T11:13:43Z"],
        alias="lastChangeDate",
    )
    access_rights: Dict[GroupID, AccessRights] = Field(
        ...,
        description="object containing the GroupID as key and read/write/execution permissions as value",
        alias="accessRights",
    )

    # Classification
    tags: Optional[List[int]] = []
    classifiers: Optional[List[ClassifierID]] = Field(
        default_factory=list,
        description="Contains the reference to the project classifiers",
        examples=["some:id:to:a:classifier"],
    )

    # Project state (SEE projects_state.py)
    state: Optional[ProjectState] = None

    # UI front-end setup (SEE projects_ui.py)
    ui: Optional[StudyUI] = None

    # Quality
    quality: Dict[str, Any] = Field(
        {}, description="stores the study quality assessment"
    )

    # Dev only
    dev: Optional[Dict] = Field(description="object used for development purposes only")

    class Config:
        description = "Document that stores metadata, pipeline and UI setup of a study"
        title = "osparc-simcore project"
        extra = Extra.forbid

        @staticmethod
        def schema_extra(schema: Dict, _model: "Project"):
            # pylint: disable=unsubscriptable-object

            # Patch to allow jsonschema nullable
            # SEE https://github.com/samuelcolvin/pydantic/issues/990#issuecomment-645961530
            state_pydantic_schema = deepcopy(schema["properties"]["state"])
            schema["properties"]["state"] = {
                "anyOf": [{"type": "null"}, state_pydantic_schema]
            }
