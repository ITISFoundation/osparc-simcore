from datetime import datetime
from enum import Enum
from typing import Any, TypeAlias

from aiopg.sa.result import RowProxy
from models_library.api_schemas_webserver.projects import ProjectPatch
from models_library.folders import FolderID
from models_library.projects import ClassifierID, ProjectID
from models_library.projects_ui import StudyUI
from models_library.users import UserID
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator
from simcore_postgres_database.models.projects import ProjectType, projects

ProjectDict: TypeAlias = dict[str, Any]
ProjectProxy: TypeAlias = RowProxy


class ProjectTypeAPI(str, Enum):
    all = "all"
    template = "template"
    user = "user"

    @classmethod
    def to_project_type_db(cls, api_type: "ProjectTypeAPI") -> ProjectType | None:
        return {
            ProjectTypeAPI.all: None,
            ProjectTypeAPI.template: ProjectType.TEMPLATE,
            ProjectTypeAPI.user: ProjectType.STANDARD,
        }[api_type]


class ProjectDB(BaseModel):
    id: int
    type: ProjectType
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrl | None
    prj_owner: UserID
    creation_date: datetime
    last_change_date: datetime
    ui: StudyUI | None
    classifiers: list[ClassifierID]
    dev: dict | None
    quality: dict[str, Any]
    published: bool
    hidden: bool
    workspace_id: WorkspaceID | None
    trashed_at: datetime | None
    trashed_explicitly: bool = False

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    # validators
    _empty_thumbnail_is_none = field_validator("thumbnail", mode="before")(
        empty_str_to_none_pre_validator
    )
    _none_description_is_empty = field_validator("description", mode="before")(
        none_to_empty_str_pre_validator
    )


class UserSpecificProjectDataDB(ProjectDB):
    folder_id: FolderID | None

    model_config = ConfigDict(from_attributes=True)


assert set(ProjectDB.model_fields.keys()).issubset(  # nosec
    {c.name for c in projects.columns if c.name not in ["access_rights"]}
)


class UserProjectAccessRightsDB(BaseModel):
    uid: UserID
    read: bool
    write: bool
    delete: bool
    model_config = ConfigDict(from_attributes=True)


class UserProjectAccessRightsWithWorkspace(BaseModel):
    uid: UserID
    workspace_id: WorkspaceID | None  # None if it's a private workspace
    read: bool
    write: bool
    delete: bool
    model_config = ConfigDict(from_attributes=True)


class ProjectPatchExtended(ProjectPatch):
    # Only used internally
    trashed_at: datetime | None
    trashed_explicitly: bool

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


__all__: tuple[str, ...] = (
    "ProjectDict",
    "ProjectProxy",
)
