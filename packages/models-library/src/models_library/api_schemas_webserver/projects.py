"""rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

import copy
from datetime import datetime
from typing import Annotated, Any, Literal, Self, TypeAlias

from common_library.basic_types import DEFAULT_FACTORY
from common_library.dict_tools import remap_keys
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    PlainSerializer,
    field_validator,
)
from pydantic.config import JsonDict

from ..api_schemas_long_running_tasks.tasks import TaskGet
from ..basic_types import LongTruncatedStr, ShortTruncatedStr
from ..emails import LowerCaseEmailStr
from ..folders import FolderID
from ..groups import GroupID
from ..projects import (
    ClassifierID,
    DateTimeStr,
    NodesDict,
    ProjectID,
    ProjectTemplateType,
    ProjectType,
)
from ..projects_access import AccessRights, GroupIDStr
from ..projects_state import (
    ProjectShareCurrentUserGroupIDs,
    ProjectShareLocked,
    ProjectShareStatus,
    ProjectStateRunningState,
)
from ..utils._original_fastapi_encoders import jsonable_encoder
from ..utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
    null_or_none_str_to_none_validator,
)
from ..workspaces import WorkspaceID
from ._base import EmptyModel, InputSchema, OutputSchema
from .permalinks import ProjectPermalink
from .projects_ui import StudyUI


class ProjectCreateNew(InputSchema):
    uuid: ProjectID | None = None  # NOTE: suggested uuid! but could be different!

    # display
    name: str
    description: str | None = None
    thumbnail: HttpUrl | None = None

    workbench: NodesDict

    access_rights: dict[GroupIDStr, AccessRights]

    tags: Annotated[list[int], Field(default_factory=list)] = DEFAULT_FACTORY
    classifiers: Annotated[list[ClassifierID], Field(default_factory=list)] = (
        DEFAULT_FACTORY
    )

    ui: StudyUI | None = None

    workspace_id: WorkspaceID | None = None
    folder_id: FolderID | None = None

    _empty_is_none = field_validator("uuid", "thumbnail", "description", mode="before")(
        empty_str_to_none_pre_validator
    )

    _null_or_none_to_none = field_validator("workspace_id", "folder_id", mode="before")(
        null_or_none_str_to_none_validator
    )

    def to_domain_model(self) -> dict[str, Any]:
        return self.model_dump(
            exclude_unset=True,
            by_alias=True,
            exclude_none=True,
        )


# NOTE: based on OVERRIDABLE_DOCUMENT_KEYS
class ProjectCopyOverride(InputSchema):
    name: str
    description: str | None = None
    thumbnail: HttpUrl | None = None
    prj_owner: LowerCaseEmailStr

    _empty_is_none = field_validator("thumbnail", mode="before")(
        empty_str_to_none_pre_validator
    )

    def to_domain_model(self) -> dict[str, Any]:
        return self.model_dump(
            exclude_unset=True,
            by_alias=True,
            exclude_none=True,
        )


class ProjectShareStateOutputSchema(OutputSchema):
    status: ProjectShareStatus
    locked: ProjectShareLocked
    current_user_groupids: ProjectShareCurrentUserGroupIDs


class ProjectStateOutputSchema(OutputSchema):
    share_state: ProjectShareStateOutputSchema
    state: ProjectStateRunningState


class ProjectGet(OutputSchema):
    uuid: ProjectID

    # display
    name: str
    description: str
    thumbnail: HttpUrl | Literal[""]

    type: ProjectType
    template_type: ProjectTemplateType | None

    workbench: NodesDict

    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]

    # state
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    state: ProjectStateOutputSchema | None = None
    trashed_at: datetime | None
    trashed_by: Annotated[
        GroupID | None, Field(description="The primary gid of the user who trashed")
    ]

    # labeling
    tags: list[int]
    classifiers: Annotated[
        list[ClassifierID],
        Field(default_factory=list, json_schema_extra={"default": []}),
    ] = DEFAULT_FACTORY

    quality: Annotated[
        dict[str, Any], Field(default_factory=dict, json_schema_extra={"default": {}})
    ] = DEFAULT_FACTORY

    # front-end
    ui: EmptyModel | StudyUI | None = None
    dev: dict | None

    permalink: ProjectPermalink | None = None

    workspace_id: WorkspaceID | None
    folder_id: FolderID | None

    _empty_description = field_validator("description", mode="before")(
        none_to_empty_str_pre_validator
    )

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            examples=[
                {
                    "uuid": "a8b0f384-bd08-4793-ab25-65d5a755f4b6",
                    "name": "My Project",
                    "description": "This is a sample project",
                    "thumbnail": "https://example.com/thumbnail.png",
                    "type": "STANDARD",
                    "template_type": None,
                    "workbench": {},
                    "prj_owner": "user@email.com",
                    "access_rights": {},
                    "trashed_at": None,
                    "trashed_by": None,
                    "dev": {},
                    "tags": [],
                    "workspace_id": None,
                    "folder_id": None,
                    "creation_date": "2023-01-01T00:00:00Z",
                    "last_change_date": "2023-01-02T00:00:00Z",
                }
            ]
        )

    model_config = ConfigDict(frozen=False, json_schema_extra=_update_json_schema_extra)

    @classmethod
    def from_domain_model(cls, project_data: dict[str, Any]) -> Self:
        trimmed_data = copy.deepcopy(project_data)
        # NOTE: project_data["trashed_by"] is a UserID
        # NOTE: project_data["trashed_by_primary_gid"] is a GroupID
        trimmed_data.pop("trashed_by", None)
        trimmed_data.pop("trashedBy", None)

        return cls.model_validate(
            remap_keys(
                trimmed_data,
                rename={
                    "trashed": "trashed_at",
                    "trashed_by_primary_gid": "trashed_by",
                    "trashedByPrimaryGid": "trashedBy",
                },
            )
        )


TaskProjectGet: TypeAlias = TaskGet


class ProjectListItem(ProjectGet): ...


class ProjectReplace(InputSchema):
    uuid: ProjectID

    name: ShortTruncatedStr
    description: LongTruncatedStr
    thumbnail: Annotated[
        HttpUrl | None,
        BeforeValidator(empty_str_to_none_pre_validator),
    ] = None

    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]

    tags: Annotated[
        list[int] | None, Field(default_factory=list, json_schema_extra={"default": []})
    ] = DEFAULT_FACTORY

    classifiers: Annotated[
        list[ClassifierID] | None,
        Field(default_factory=list, json_schema_extra={"default": []}),
    ] = DEFAULT_FACTORY

    ui: StudyUI | None = None

    quality: Annotated[
        dict[str, Any], Field(default_factory=dict, json_schema_extra={"default": {}})
    ] = DEFAULT_FACTORY


class ProjectPatch(InputSchema):
    name: ShortTruncatedStr | None = None
    description: LongTruncatedStr | None = None
    thumbnail: Annotated[
        HttpUrl | None,
        BeforeValidator(empty_str_to_none_pre_validator),
        PlainSerializer(lambda x: str(x) if x is not None else None),
    ] = None

    access_rights: dict[GroupIDStr, AccessRights] | None = None
    classifiers: list[ClassifierID] | None = None
    dev: dict | None = None
    ui: Annotated[
        StudyUI | None,
        BeforeValidator(empty_str_to_none_pre_validator),
        PlainSerializer(
            lambda obj: jsonable_encoder(
                obj, exclude_unset=True, by_alias=False
            )  # For the sake of backward compatibility
        ),
    ] = None
    quality: dict[str, Any] | None = None
    template_type: ProjectTemplateType | None = None
    hidden: bool | None = None

    def to_domain_model(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True, by_alias=False)


class ProjectDocument(OutputSchema):
    uuid: ProjectID
    workspace_id: WorkspaceID | None
    name: str
    description: str
    thumbnail: HttpUrl | None
    last_change_date: datetime
    classifiers: list[ClassifierID]
    dev: dict | None
    quality: dict[str, Any]
    workbench: NodesDict
    ui: StudyUI | None
    type: ProjectType
    template_type: ProjectTemplateType | None

    # config
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


ProjectDocumentVersion: TypeAlias = int


__all__: tuple[str, ...] = (
    "EmptyModel",
    "ProjectCopyOverride",
    "ProjectCreateNew",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "TaskProjectGet",
)
