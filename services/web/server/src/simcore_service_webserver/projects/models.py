from datetime import datetime
from enum import Enum
from typing import Any, TypeAlias

from aiopg.sa.result import RowProxy
from common_library.dict_tools import remap_keys
from models_library.api_schemas_webserver.projects import ProjectPatch
from models_library.api_schemas_webserver.projects_ui import StudyUI
from models_library.folders import FolderID
from models_library.groups import GroupID
from models_library.projects import ClassifierID, NodesDict, ProjectID
from models_library.users import UserID
from models_library.utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)
from models_library.workspaces import WorkspaceID
from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator
from simcore_postgres_database.models.projects import ProjectTemplateType, ProjectType

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


class ProjectDBGet(BaseModel):
    # NOTE: model intented to read one-to-one columns of the `projects` table
    id: int
    type: ProjectType
    template_type: ProjectTemplateType | None
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrl | None
    prj_owner: UserID  # == user.id (who created)
    creation_date: datetime
    last_change_date: datetime
    ui: StudyUI | None
    classifiers: list[ClassifierID]
    dev: dict | None
    quality: dict[str, Any]
    published: bool
    hidden: bool
    workspace_id: WorkspaceID | None

    trashed: datetime | None
    trashed_by: UserID | None  # == user.id (who trashed)
    trashed_explicitly: bool = False

    # config
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

    # validators
    _empty_thumbnail_is_none = field_validator("thumbnail", mode="before")(
        empty_str_to_none_pre_validator
    )
    _none_description_is_empty = field_validator("description", mode="before")(
        none_to_empty_str_pre_validator
    )


class ProjectJobDBGet(ProjectDBGet):
    workbench: NodesDict

    job_parent_resource_name: str


class ProjectWithTrashExtra(ProjectDBGet):
    # This field is not part of the tables
    trashed_by_primary_gid: GroupID | None = None


class UserSpecificProjectDataDBGet(ProjectDBGet):
    folder_id: FolderID | None

    model_config = ConfigDict(from_attributes=True)


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


class ProjectPatchInternalExtended(ProjectPatch):
    # ONLY used internally
    trashed_at: datetime | None
    trashed_by: UserID | None
    trashed_explicitly: bool

    model_config = ConfigDict(validate_by_name=True, extra="forbid")

    def to_domain_model(self) -> dict[str, Any]:
        return remap_keys(
            self.model_dump(exclude_unset=True, by_alias=False),
            rename={"trashed_at": "trashed"},
        )
