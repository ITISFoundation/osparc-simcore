from datetime import datetime
from typing import Annotated, Self

from pydantic import ConfigDict, Field, field_validator

from ..access_rights import AccessRights
from ..basic_types import IDStr
from ..folders import FolderDB, FolderID
from ..groups import GroupID
from ..utils.common_validators import null_or_none_str_to_none_validator
from ..workspaces import WorkspaceID
from ._base import InputSchema, OutputSchema


class FolderGet(OutputSchema):
    folder_id: FolderID
    parent_folder_id: FolderID | None = None
    name: str

    created_at: datetime
    modified_at: datetime
    trashed_at: datetime | None
    trashed_by: Annotated[
        GroupID | None, Field(description="The primary gid of the user who trashed")
    ]
    owner: GroupID
    workspace_id: WorkspaceID | None
    my_access_rights: AccessRights

    @classmethod
    def from_domain_model(
        cls,
        folder_db: FolderDB,
        trashed_by_primary_gid: GroupID | None,
        user_folder_access_rights: AccessRights,
    ) -> Self:
        if (folder_db.trashed_by is None) ^ (trashed_by_primary_gid is None):
            msg = f"Incompatible inputs: {folder_db.trashed_by=} but not {trashed_by_primary_gid=}"
            raise ValueError(msg)

        return cls(
            folder_id=folder_db.folder_id,
            parent_folder_id=folder_db.parent_folder_id,
            name=folder_db.name,
            created_at=folder_db.created,
            modified_at=folder_db.modified,
            trashed_at=folder_db.trashed,
            trashed_by=trashed_by_primary_gid,
            owner=folder_db.created_by_gid,
            workspace_id=folder_db.workspace_id,
            my_access_rights=user_folder_access_rights,
        )


class FolderCreateBodyParams(InputSchema):
    name: IDStr
    parent_folder_id: FolderID | None = None
    workspace_id: WorkspaceID | None = None
    model_config = ConfigDict(extra="forbid")

    _null_or_none_str_to_none_validator = field_validator(
        "parent_folder_id", mode="before"
    )(null_or_none_str_to_none_validator)

    _null_or_none_str_to_none_validator2 = field_validator(
        "workspace_id", mode="before"
    )(null_or_none_str_to_none_validator)


class FolderReplaceBodyParams(InputSchema):
    name: IDStr
    parent_folder_id: FolderID | None = None
    model_config = ConfigDict(extra="forbid")

    _null_or_none_str_to_none_validator = field_validator(
        "parent_folder_id", mode="before"
    )(null_or_none_str_to_none_validator)
