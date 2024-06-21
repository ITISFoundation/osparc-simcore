""" rest API schema models for projects


SEE rationale in https://fastapi.tiangolo.com/tutorial/extra-models/#multiple-models

"""

from typing import Any, Literal, TypeAlias

from pydantic import ConstrainedStr, Field, validator

from ..api_schemas_long_running_tasks.tasks import TaskGet
from ..basic_types import HttpUrlWithCustomMinLength
from ..emails import LowerCaseEmailStr
from ..projects import ClassifierID, DateTimeStr, NodesDict, ProjectID
from ..projects_access import AccessRights, GroupIDStr
from ..projects_state import ProjectState
from ..projects_ui import StudyUI
from ..utils.common_validators import (
    empty_str_to_none_pre_validator,
    none_to_empty_str_pre_validator,
)
from ..utils.pydantic_tools_extension import FieldNotRequired
from ._base import EmptyModel, InputSchema, OutputSchema
from .permalinks import ProjectPermalink


class ProjectCreateNew(InputSchema):
    uuid: ProjectID | None = None  # NOTE: suggested uuid! but could be different!
    name: str
    description: str | None
    thumbnail: HttpUrlWithCustomMinLength | None
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] = Field(default_factory=list)
    classifiers: list[ClassifierID] = Field(default_factory=list)
    ui: StudyUI | None = None

    _empty_is_none = validator(
        "uuid", "thumbnail", "description", allow_reuse=True, pre=True
    )(empty_str_to_none_pre_validator)


# NOTE: based on OVERRIDABLE_DOCUMENT_KEYS
class ProjectCopyOverride(InputSchema):
    name: str
    description: str | None
    thumbnail: HttpUrlWithCustomMinLength | None
    prj_owner: LowerCaseEmailStr

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )


class ProjectGet(OutputSchema):
    uuid: ProjectID
    name: str
    description: str
    thumbnail: HttpUrlWithCustomMinLength | Literal[""]
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    prj_owner: LowerCaseEmailStr
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int]
    classifiers: list[ClassifierID] = []
    state: ProjectState | None
    ui: EmptyModel | StudyUI | None
    quality: dict[str, Any] = {}
    dev: dict | None
    permalink: ProjectPermalink = FieldNotRequired()

    _empty_description = validator("description", allow_reuse=True, pre=True)(
        none_to_empty_str_pre_validator
    )


TaskProjectGet: TypeAlias = TaskGet


class ProjectListItem(ProjectGet):
    ...


class TitleStr(ConstrainedStr):
    # Truncate title strings that exceed the specified characters limit (curtail_length).
    # This ensures the **input** to the API is controlled and prevents exceeding
    # the database's constraints without causing errors.
    curtail_length = 200
    strip_whitespace = True


class DescriptionStr(ConstrainedStr):
    # Truncate description strings that exceed the specified characters limit (curtail_length).
    curtail_length = 1000
    strip_whitespace = True


class ProjectReplace(InputSchema):
    uuid: ProjectID
    name: TitleStr
    description: DescriptionStr
    thumbnail: HttpUrlWithCustomMinLength | None
    creation_date: DateTimeStr
    last_change_date: DateTimeStr
    workbench: NodesDict
    access_rights: dict[GroupIDStr, AccessRights]
    tags: list[int] | None = []
    classifiers: list[ClassifierID] | None = Field(
        default_factory=list,
    )
    ui: StudyUI | None = None
    quality: dict[str, Any] = Field(
        default_factory=dict,
    )

    _empty_is_none = validator("thumbnail", allow_reuse=True, pre=True)(
        empty_str_to_none_pre_validator
    )


class ProjectUpdate(InputSchema):
    name: TitleStr = FieldNotRequired()
    description: DescriptionStr = FieldNotRequired()
    thumbnail: HttpUrlWithCustomMinLength = FieldNotRequired()
    workbench: NodesDict = FieldNotRequired()
    access_rights: dict[GroupIDStr, AccessRights] = FieldNotRequired()
    tags: list[int] = FieldNotRequired()
    classifiers: list[ClassifierID] = FieldNotRequired()
    ui: StudyUI | None = None
    quality: dict[str, Any] = FieldNotRequired()


class ProjectPatch(InputSchema):
    name: TitleStr = FieldNotRequired()
    description: DescriptionStr = FieldNotRequired()
    thumbnail: HttpUrlWithCustomMinLength = FieldNotRequired()
    access_rights: dict[GroupIDStr, AccessRights] = FieldNotRequired()
    classifiers: list[ClassifierID] = FieldNotRequired()
    dev: dict | None = FieldNotRequired()
    ui: StudyUI | None = FieldNotRequired()
    quality: dict[str, Any] = FieldNotRequired()


__all__: tuple[str, ...] = (
    "EmptyModel",
    "ProjectCopyOverride",
    "ProjectCreateNew",
    "ProjectGet",
    "ProjectListItem",
    "ProjectReplace",
    "ProjectUpdate",
    "TaskProjectGet",
)
