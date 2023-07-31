"""
    Models a study's project document
"""
import re
from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import Any, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConstrainedStr, Extra, Field, validator

from .basic_regex import DATE_RE, UUID_RE_BASE
from .basic_types import HttpUrlWithCustomMinLength
from .emails import LowerCaseEmailStr
from .projects_access import AccessRights, GroupIDStr
from .projects_nodes import Node
from .projects_nodes_io import NodeIDStr
from .projects_state import ProjectState
from .projects_ui import StudyUI
from .utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)

ProjectID: TypeAlias = UUID
ClassifierID: TypeAlias = str

NodesDict: TypeAlias = dict[NodeIDStr, Node]


class ProjectIDStr(ConstrainedStr):
    regex = re.compile(UUID_RE_BASE)

    class Config:
        frozen = True


class DateTimeStr(ConstrainedStr):
    regex = re.compile(DATE_RE)

    class Config:
        frozen = True


# NOTE: careful this is in sync with packages/postgres-database/src/simcore_postgres_database/models/projects.py!!!
class ProjectType(str, Enum):
    TEMPLATE = "TEMPLATE"
    STANDARD = "STANDARD"


class BaseProjectModel(BaseModel):
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
    thumbnail: HttpUrlWithCustomMinLength | None = Field(
        ...,
        description="url of the project thumbnail",
        examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
    )

    creation_date: datetime = Field(...)
    last_change_date: datetime = Field(...)

    # Pipeline of nodes (SEE projects_nodes.py)
    workbench: NodesDict = Field(..., description="Project's pipeline")

    # validators
    _empty_thumbnail_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )

    _none_description_is_empty = validator("description", allow_reuse=True, pre=True)(
        none_to_empty_str_pre_validator
    )


class ProjectAtDB(BaseProjectModel):
    # Model used to READ from database

    id: int = Field(..., description="The table primary index")

    project_type: ProjectType = Field(..., alias="type", description="The project type")

    prj_owner: int | None = Field(..., description="The project owner id")

    published: bool | None = Field(
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
        allow_population_by_field_name = True


class Project(BaseProjectModel):
    # NOTE: This is the pydantic pendant of project-v0.0.1.json used in the API of the webserver/webclient
    # NOT for usage with DB!!

    # Ownership and Access  (SEE projects_access.py)
    prj_owner: LowerCaseEmailStr = Field(
        ..., description="user email", alias="prjOwner"
    )

    # Timestamps
    creation_date: DateTimeStr = Field(  # type: ignore[assignment]
        ...,
        description="project creation date",
        examples=["2018-07-01T11:13:43Z"],
        alias="creationDate",
    )
    last_change_date: DateTimeStr = Field(  # type: ignore[assignment]
        ...,
        description="last save date",
        examples=["2018-07-01T11:13:43Z"],
        alias="lastChangeDate",
    )
    access_rights: dict[GroupIDStr, AccessRights] = Field(
        ...,
        description="object containing the GroupID as key and read/write/execution permissions as value",
        alias="accessRights",
    )

    # Classification
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(
        default_factory=list,
        description="Contains the reference to the project classifiers",
        examples=["some:id:to:a:classifier"],
    )

    # Project state (SEE projects_state.py)
    state: ProjectState | None = None

    # UI front-end setup (SEE projects_ui.py)
    ui: StudyUI | None = None

    # Quality
    quality: dict[str, Any] = Field(
        default_factory=dict,
        description="stores the study quality assessment",
    )

    # Dev only
    dev: dict | None = Field(
        default=None, description="object used for development purposes only"
    )

    class Config:
        description = "Document that stores metadata, pipeline and UI setup of a study"
        title = "osparc-simcore project"
        extra = Extra.forbid

        @staticmethod
        def schema_extra(schema: dict, _model: "Project"):
            # pylint: disable=unsubscriptable-object

            # Patch to allow jsonschema nullable
            # SEE https://github.com/samuelcolvin/pydantic/issues/990#issuecomment-645961530
            state_pydantic_schema = deepcopy(schema["properties"]["state"])
            schema["properties"]["state"] = {
                "anyOf": [{"type": "null"}, state_pydantic_schema]
            }
