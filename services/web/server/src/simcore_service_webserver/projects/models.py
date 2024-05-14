from datetime import datetime
from enum import Enum
from typing import Any, TypeAlias

from aiopg.sa.result import RowProxy
from models_library.basic_types import HttpUrlWithCustomMinLength
from models_library.projects import ClassifierID, ProjectID
from models_library.projects_access import AccessRights, GroupIDStr
from models_library.projects_ui import StudyUI
from models_library.users import UserID
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)
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
    access_rights: dict[GroupIDStr, AccessRights]
    ui: StudyUI | None
    classifiers: list[ClassifierID]
    dev: dict | None
    quality: dict[str, Any]
    published: bool
    hidden: bool

    class Config:
        orm_mode = True

    # validators
    _empty_thumbnail_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )
    _none_description_is_empty = validator("description", allow_reuse=True, pre=True)(
        none_to_empty_str_pre_validator
    )


assert set(ProjectDB.__fields__.keys()).issubset(  # nosec
    {c.name for c in projects.columns}
)


class UserProjectAccessRights(BaseModel):
    uid: UserID
    read: bool
    write: bool
    delete: bool

    class Config:
        orm_mode = True


__all__: tuple[str, ...] = (
    "ProjectDict",
    "ProjectProxy",
)
