from datetime import datetime
from enum import Enum
from typing import Any, TypeAlias

from aiopg.sa.result import RowProxy
from models_library.basic_types import HttpUrlWithCustomMinLength
from models_library.folders import FolderID
from models_library.projects import ClassifierID, ProjectID
from models_library.projects_ui import StudyUI
from models_library.users import UserID
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, validator
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
    thumbnail: HttpUrlWithCustomMinLength | None
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

    class Config:
        orm_mode = True

    # validators
    _empty_thumbnail_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )
    _none_description_is_empty = validator("description", allow_reuse=True, pre=True)(
        none_to_empty_str_pre_validator
    )


class UserSpecificProjectDataDB(ProjectDB):
    folder_id: FolderID | None

    class Config:
        orm_mode = True


assert set(ProjectDB.__fields__.keys()).issubset(  # nosec
    {c.name for c in projects.columns if c.name not in ["access_rights"]}
)


class UserProjectAccessRightsDB(BaseModel):
    uid: UserID
    read: bool
    write: bool
    delete: bool

    class Config:
        orm_mode = True


class UserProjectAccessRightsWithWorkspace(BaseModel):
    uid: UserID
    workspace_id: WorkspaceID | None  # None if it's a private workspace
    read: bool
    write: bool
    delete: bool

    class Config:
        orm_mode = True


__all__: tuple[str, ...] = (
    "ProjectDict",
    "ProjectProxy",
)
