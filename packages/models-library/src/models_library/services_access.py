"""Service access rights models

"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from .groups import GroupID
from .utils.change_case import snake_to_camel


class ServiceGroupAccessRights(BaseModel):
    execute_access: Annotated[
        bool, Field(description="defines whether the group can execute the service")
    ] = False
    write_access: Annotated[
        bool, Field(description="defines whether the group can modify the service")
    ] = False


class ServiceGroupAccessRightsV2(BaseModel):
    execute: bool = False
    write: bool = False

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ServiceAccessRights(BaseModel):
    access_rights: Annotated[
        dict[GroupID, ServiceGroupAccessRights] | None,
        Field(
            alias="accessRights",
            description="service access rights per group id",
        ),
    ] = None
