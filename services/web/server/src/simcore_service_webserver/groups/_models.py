import logging
from typing import Literal

from models_library.rest_base import RequestParameters, StrictRequestParameters
from models_library.users import GroupID, UserID
from pydantic import Field

from .._constants import RQ_PRODUCT_KEY, RQT_USERID_KEY

_logger = logging.getLogger(__name__)


class GroupsRequestContext(RequestParameters):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


class GroupsPathParams(StrictRequestParameters):
    gid: GroupID


class GroupsUsersPathParams(StrictRequestParameters):
    gid: GroupID
    uid: UserID


class GroupsClassifiersQuery(RequestParameters):
    tree_view: Literal["std"] = "std"
