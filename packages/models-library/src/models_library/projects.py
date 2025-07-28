"""
Models a study's project document
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Final, TypeAlias
from uuid import UUID

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
)

from .basic_regex import DATE_RE, UUID_RE_BASE
from .basic_types import ConstrainedStr
from .emails import LowerCaseEmailStr
from .folders import FolderID
from .groups import GroupID
from .products import ProductName
from .projects_access import AccessRights, GroupIDStr
from .projects_nodes import Node
from .projects_nodes_io import NodeIDStr
from .projects_state import ProjectState
from .users import UserID
from .utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)
from .utils.enums import StrAutoEnum
from .workspaces import WorkspaceID

ProjectID: TypeAlias = UUID
CommitID: TypeAlias = int
ClassifierID: TypeAlias = str

NodesDict: TypeAlias = dict[NodeIDStr, Node]
_DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S.%fZ"


ProjectIDStr: TypeAlias = Annotated[str, StringConstraints(pattern=UUID_RE_BASE)]


class DateTimeStr(ConstrainedStr):
    pattern = DATE_RE

    @classmethod
    def to_datetime(cls, s: "DateTimeStr"):
        return datetime.strptime(s, _DATETIME_FORMAT)


# NOTE: careful this is in sync with packages/postgres-database/src/simcore_postgres_database/models/projects.py!!!
class ProjectType(str, Enum):
    TEMPLATE = "TEMPLATE"
    STANDARD = "STANDARD"


class ProjectTemplateType(StrAutoEnum):
    TEMPLATE = "TEMPLATE"
    TUTORIAL = "TUTORIAL"
    HYPERTOOL = "HYPERTOOL"


class BaseProjectModel(BaseModel):
    # Description of the project
    uuid: Annotated[
        ProjectID,
        Field(
            description="project unique identifier",
            examples=[
                "07640335-a91f-468c-ab69-a374fa82078d",
                "9bcf8feb-c1b1-41b6-b201-639cd6ccdba8",
            ],
        ),
    ]

    name: Annotated[
        str,
        Field(description="project name", examples=["Temporal Distortion Simulator"]),
    ]
    description: Annotated[
        str,
        Field(
            description="longer one-line description about the project",
            examples=["Dabbling in temporal transitions ..."],
        ),
    ]
    thumbnail: Annotated[
        HttpUrl | None,
        Field(
            description="url of the project thumbnail",
            examples=["https://placeimg.com/171/96/tech/grayscale/?0.jpg"],
        ),
    ]

    creation_date: datetime
    last_change_date: datetime

    # Pipeline of nodes (SEE projects_nodes.py)
    # FIXME: pedro removes this one
    workbench: Annotated[NodesDict, Field(description="Project's pipeline")]

    # validators
    _empty_thumbnail_is_none = field_validator("thumbnail", mode="before")(
        empty_str_to_none_pre_validator
    )

    _none_description_is_empty = field_validator("description", mode="before")(
        none_to_empty_str_pre_validator
    )


class ProjectAtDB(BaseProjectModel):
    # Model used to READ from database

    id: Annotated[int, Field(description="The table primary index")]

    project_type: Annotated[
        ProjectType, Field(alias="type", description="The project type")
    ]
    template_type: Annotated[
        ProjectTemplateType | None,
        Field(
            examples=["TEMPLATE", "TUTORIAL", "HYPERTOOL", None],
        ),
    ]

    prj_owner: Annotated[int | None, Field(description="The project owner id")]

    published: Annotated[
        bool | None,
        Field(description="Defines if a study is available publicly"),
    ] = False

    @field_validator("project_type", mode="before")
    @classmethod
    def _convert_sql_alchemy_enum(cls, v):
        if isinstance(v, Enum):
            return v.value
        return v

    model_config = ConfigDict(
        from_attributes=True, use_enum_values=True, populate_by_name=True
    )


class ProjectListAtDB(BaseProjectModel):
    id: int
    type: ProjectType
    template_type: ProjectTemplateType | None
    prj_owner: int | None
    ui: dict[str, Any] | None
    classifiers: list[ClassifierID] | None
    dev: dict[str, Any] | None
    quality: dict[str, Any]
    published: bool | None
    hidden: bool
    workspace_id: WorkspaceID | None
    trashed: datetime | None
    trashed_by: UserID | None
    trashed_explicitly: bool
    product_name: ProductName
    folder_id: FolderID | None


class Project(BaseProjectModel):
    # NOTE: This is the pydantic pendant of project-v0.0.1.json used in the API of the webserver/webclient
    # NOT for usage with DB!!

    # Ownership and Access  (SEE projects_access.py)
    prj_owner: Annotated[
        LowerCaseEmailStr, Field(description="user email", alias="prjOwner")
    ]
    access_rights: Annotated[
        dict[GroupIDStr, AccessRights],
        Field(
            description="object containing the GroupID as key and read/write/execution permissions as value",
            alias="accessRights",
        ),
    ]

    # Lifecycle
    creation_date: Annotated[  # type: ignore[assignment]
        DateTimeStr,
        Field(
            description="project creation date",
            examples=["2018-07-01T11:13:43Z"],
            alias="creationDate",
        ),
    ]
    last_change_date: Annotated[  # type: ignore[assignment]
        DateTimeStr,
        Field(
            description="last save date",
            examples=["2018-07-01T11:13:43Z"],
            alias="lastChangeDate",
        ),
    ]

    # Project state (SEE projects_state.py)
    state: ProjectState | None = None

    # Type of project
    type: Annotated[
        ProjectType,
        Field(
            description="The project type",
            examples=["TEMPLATE", "STANDARD"],
        ),
    ]
    template_type: Annotated[
        ProjectTemplateType | None,
        Field(
            alias="templateType",
            examples=["TEMPLATE", "TUTORIAL", "HYPERTOOL", None],
        ),
    ]

    # UI front-end fields (SEE projects_ui.py)
    ui: dict[str, Any] | None = None
    dev: dict[str, Any] | None = None

    # Parenthood
    workspace_id: Annotated[
        WorkspaceID | None,
        Field(
            description="To which workspace project belongs. If None, belongs to private user workspace.",
            alias="workspaceId",
        ),
    ] = None

    folder_id: Annotated[
        FolderID | None,
        Field(
            description="To which folder project belongs. If None, belongs to root folder.",
            alias="folderId",
        ),
    ] = None

    # trash state
    trashed: datetime | None = None
    trashed_by: Annotated[UserID | None, Field(alias="trashedBy")] = None
    trashed_by_primary_gid: Annotated[
        GroupID | None, Field(alias="trashedByPrimaryGid")
    ] = None
    trashed_explicitly: Annotated[bool, Field(alias="trashedExplicitly")] = False

    # Labeling
    tags: Annotated[list[int] | None, Field(default_factory=list)] = DEFAULT_FACTORY
    classifiers: Annotated[
        list[ClassifierID] | None,
        Field(
            default_factory=list,
            description="Contains the reference to the project classifiers",
            examples=["some:id:to:a:classifier"],
        ),
    ] = DEFAULT_FACTORY
    quality: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="stores the study quality assessment",
        ),
    ] = DEFAULT_FACTORY

    model_config = ConfigDict(
        # NOTE: this is a security measure until we get rid of the ProjectDict variants
        extra="forbid",
        populate_by_name=True,
    )
