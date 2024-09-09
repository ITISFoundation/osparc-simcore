from contextlib import suppress

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    parse_obj_as,
)

from ..emails import LowerCaseEmailStr

#
# GROUPS MODELS defined in OPENAPI specs
#


class GroupAccessRights(BaseModel):
    """
    defines acesss rights for the user
    """

    read: bool
    write: bool
    delete: bool
    model_config = ConfigDict()


class UsersGroup(BaseModel):
    gid: int = Field(..., description="the group ID")
    label: str = Field(..., description="the group name")
    description: str = Field(..., description="the group description")
    thumbnail: AnyUrl | None = Field(
        default=None, description="url to the group thumbnail"
    )
    access_rights: GroupAccessRights = Field(..., alias="accessRights")
    inclusion_rules: dict[str, str] = Field(
        default_factory=dict,
        description="Maps user's column and regular expression",
        alias="inclusionRules",
    )

    @field_validator("thumbnail", mode="before")
    @classmethod
    @classmethod
    def sanitize_legacy_data(cls, v):
        if v:
            # Enforces null if thumbnail is not valid URL or empty
            with suppress(ValidationError):
                return parse_obj_as(AnyUrl, v)
        return None

    model_config = ConfigDict()


class AllUsersGroups(BaseModel):
    me: UsersGroup | None = None
    organizations: list[UsersGroup] | None = None
    all: UsersGroup | None = None
    product: UsersGroup | None = None
    model_config = ConfigDict()


class GroupUserGet(BaseModel):
    id: str | None = Field(None, description="the user id")
    login: LowerCaseEmailStr | None = Field(None, description="the user login email")
    first_name: str | None = Field(None, description="the user first name")
    last_name: str | None = Field(None, description="the user last name")
    gravatar_id: str | None = Field(None, description="the user gravatar id hash")
    gid: str | None = Field(None, description="the user primary gid")
    access_rights: GroupAccessRights = Field(..., alias="accessRights")
    model_config = ConfigDict()
