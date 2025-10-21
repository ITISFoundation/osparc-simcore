from typing import Self

from common_library.groups_dicts import AccessRightsDict
from models_library.api_schemas_webserver._base import InputSchema, OutputSchema
from models_library.groups import GroupID
from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.string_types import ColorStr, DescriptionSafeStr, NameSafeStr
from models_library.users import UserID
from pydantic import Field, PositiveInt
from servicelib.aiohttp.request_keys import RQT_USERID_KEY
from simcore_postgres_database.utils_tags import TagAccessRightsDict, TagDict


class TagRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]


class TagPathParams(StrictRequestParameters):
    tag_id: PositiveInt


class TagUpdate(InputSchema):
    name: NameSafeStr | None = None
    description: DescriptionSafeStr | None = None
    color: ColorStr | None = None
    priority: int | None = None


class TagCreate(InputSchema):
    name: NameSafeStr
    description: DescriptionSafeStr | None = None
    color: ColorStr
    priority: int | None = None


class TagAccessRights(OutputSchema):
    # NOTE: analogous to GroupAccessRights
    read: bool
    write: bool
    delete: bool


class TagGet(OutputSchema):
    id: PositiveInt
    name: str
    description: str | None = None
    color: str

    # analogous to UsersGroup
    access_rights: TagAccessRights = Field(..., alias="accessRights")

    @classmethod
    def from_domain_model(cls, tag: TagDict) -> Self:
        # NOTE: cls(access_rights=tag, **tag) would also work because of Config
        return cls(
            id=tag["id"],
            name=tag["name"],
            description=tag["description"],
            color=tag["color"],
            access_rights=TagAccessRights(  # type: ignore[call-arg]
                read=tag["read"],
                write=tag["write"],
                delete=tag["delete"],
            ),
        )


#
# Share API: GROUPS
#


class TagGroupPathParams(TagPathParams):
    group_id: GroupID


class TagGroupCreate(InputSchema):
    read: bool
    write: bool
    delete: bool

    def to_domain_model(self) -> AccessRightsDict:
        data = self.model_dump()
        return AccessRightsDict(
            read=data["read"],
            write=data["write"],
            delete=data["delete"],
        )


class TagGroupGet(OutputSchema):
    gid: GroupID
    # access
    read: bool
    write: bool
    delete: bool

    @classmethod
    def from_domain_model(cls, data: TagAccessRightsDict) -> Self:
        return cls(
            gid=data["group_id"],
            read=data["read"],
            write=data["write"],
            delete=data["delete"],
        )
