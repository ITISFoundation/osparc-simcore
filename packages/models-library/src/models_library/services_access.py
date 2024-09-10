"""Service access rights models

"""

from pydantic import BaseModel, ConfigDict, Field

from .users import GroupID
from .utils.change_case import snake_to_camel


class ServiceGroupAccessRights(BaseModel):
    execute_access: bool = Field(
        default=False,
        description="defines whether the group can execute the service",
    )
    write_access: bool = Field(
        default=False, description="defines whether the group can modify the service"
    )


class ServiceGroupAccessRightsV2(BaseModel):
    execute: bool = False
    write: bool = False

    model_config = ConfigDict(
        alias_generator=snake_to_camel, populate_by_name=True, extra="forbid"
    )


class ServiceAccessRights(BaseModel):
    access_rights: dict[GroupID, ServiceGroupAccessRights] | None = Field(
        None,
        alias="accessRights",
        description="service access rights per group id",
    )
