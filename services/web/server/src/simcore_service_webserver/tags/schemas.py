import re
from datetime import datetime

from models_library.api_schemas_webserver._base import InputSchema, OutputSchema
from models_library.users import GroupID, UserID
from pydantic import ConstrainedStr, Field, PositiveInt
from servicelib.aiohttp.requests_validation import RequestParams, StrictRequestParams
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.utils_tags import TagDict


class TagRequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]


class TagPathParams(StrictRequestParams):
    tag_id: PositiveInt


class ColorStr(ConstrainedStr):
    regex = re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")


class TagUpdate(InputSchema):
    name: str | None = None
    description: str | None = None
    color: ColorStr | None = None
    priority: int | None = None


class TagCreate(InputSchema):
    name: str
    description: str | None = None
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
    def from_db(cls, tag: TagDict) -> "TagGet":
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


class TagGroupGet(OutputSchema):
    gid: GroupID
    # access
    read: bool
    write: bool
    delete: bool
    # timestamps
    created: datetime
    modified: datetime
