import functools
import logging

import pycountry
from aiohttp import web
from models_library.api_schemas_webserver._base import InputSchema, OutputSchema
from models_library.emails import LowerCaseEmailStr
from models_library.users import UserID
from pydantic import BaseModel, Field, validator
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.models.users import UserStatus

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import api
from .exceptions import UserNotFoundError
from .schemas import ProfileGet, ProfileUpdate

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class UsersRequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


def _handle_users_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except UserNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

    return wrapper


@routes.get(f"/{API_VTAG}/me", name="get_my_profile")
@login_required
@_handle_users_exceptions
async def get_my_profile(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.parse_obj(request)
    profile: ProfileGet = await api.get_user_profile(
        request.app, req_ctx.user_id, req_ctx.product_name
    )
    return envelope_json_response(profile)


@routes.put(f"/{API_VTAG}/me", name="update_my_profile")
@login_required
@permission_required("user.profile.update")
@_handle_users_exceptions
async def update_my_profile(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.parse_obj(request)
    profile_update = await parse_request_body_as(ProfileUpdate, request)
    await api.update_user_profile(request.app, req_ctx.user_id, profile_update)
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


class _SearchQueryParams(BaseModel):
    email: str


class UserProfile(OutputSchema):
    first_name: str
    last_name: str
    email: LowerCaseEmailStr
    company: str | None
    phone: str | None
    address: str
    city: str
    state: str | None = Field(description="State, province, canton, region etc")
    postal_code: str
    country: str

    # user status
    registered: bool
    status: UserStatus | None

    @validator("status")
    @classmethod
    def _consistency_check(cls, v, values):
        registered = values["registered"]
        status = v
        if not registered and status is not None:
            msg = f"{registered=} and {status=} is not allowed"
            raise ValueError(msg)
        return v


@routes.post(f"/{API_VTAG}/users:search", name="search_users")
@login_required
@permission_required("users.others.*")
@_handle_users_exceptions
async def search_users(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.parse_obj(request)
    query_params = parse_request_query_parameters_as(_SearchQueryParams, request)

    if query_params:
        raise NotImplementedError

    found: list[UserProfile] = []
    return envelope_json_response(found)


class PreUserProfile(InputSchema):
    first_name: str
    last_name: str
    email: LowerCaseEmailStr
    company: str | None
    phone: str | None
    # billing details
    address: str
    city: str
    state: str | None
    postal_code: str
    country: str

    @validator("country")
    @classmethod
    def valid_country(cls, v):
        if v:
            try:
                pycountry.countries.lookup(v)
            except LookupError as err:
                raise ValueError(v) from err
        return v


# helps sync models
assert set(PreUserProfile.__fields__).issubset(UserProfile.__fields__)  # nosec


@routes.post(f"/{API_VTAG}/users:pre-register", name="pre_register_user")
@login_required
@permission_required("users.others.*")
@_handle_users_exceptions
async def pre_register_user(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.parse_obj(request)
    user_info = await parse_request_body_as(PreUserProfile, request)

    # if user exists, no need to pre-register just returne UserProfile

    # user : UserProfile

    raise NotImplementedError
