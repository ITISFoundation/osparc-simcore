from datetime import datetime

from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.workspaces import WorkspaceID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class WorkspaceDBGet(BaseModel):
    workspace_id: WorkspaceID
    name: str
    description: str | None
    owner_primary_gid: GroupID = Field(
        ...,
        description="GID of the group that owns this wallet",
    )
    thumbnail: str | None
    created: datetime = Field(
        ...,
        description="Timestamp on creation",
    )
    modified: datetime = Field(
        ...,
        description="Timestamp of last modification",
    )
    trashed: datetime | None
    trashed_by: UserID | None
    product_name: ProductName

    model_config = ConfigDict(from_attributes=True)
