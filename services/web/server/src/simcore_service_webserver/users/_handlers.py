import functools
import logging

from aiohttp import web
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _api, api
from ._schemas import PreUserProfile
from .exceptions import AlreadyPreRegisteredError, UserNotFoundError
from .schemas import ProfileGet, ProfileUpdate

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class UsersRequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


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
    await api.update_user_profile(
        request.app, req_ctx.user_id, profile_update, as_patch=False
    )
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


class _SearchQueryParams(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=200,
        description="complete or glob pattern for an email",
    )


_RESPONSE_MODEL_MINIMAL_POLICY = RESPONSE_MODEL_POLICY.copy()
_RESPONSE_MODEL_MINIMAL_POLICY["exclude_none"] = True


@routes.get(f"/{API_VTAG}/users:search", name="search_users")
@login_required
@permission_required("user.users.*")
@_handle_users_exceptions
async def search_users(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.parse_obj(request)
    assert req_ctx.product_name  # nosec

    query_params: _SearchQueryParams = parse_request_query_parameters_as(
        _SearchQueryParams, request
    )

    found = await _api.search_users(
        request.app, email_glob=query_params.email, include_products=True
    )

    return envelope_json_response(
        [_.dict(**_RESPONSE_MODEL_MINIMAL_POLICY) for _ in found]
    )


@routes.post(f"/{API_VTAG}/users:pre-register", name="pre_register_user")
@login_required
@permission_required("user.users.*")
@_handle_users_exceptions
async def pre_register_user(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.parse_obj(request)
    pre_user_profile = await parse_request_body_as(PreUserProfile, request)

    try:
        user_profile = await _api.pre_register_user(
            request.app, profile=pre_user_profile, creator_user_id=req_ctx.user_id
        )
        return envelope_json_response(
            user_profile.dict(**_RESPONSE_MODEL_MINIMAL_POLICY)
        )
    except AlreadyPreRegisteredError as err:
        raise web.HTTPConflict(reason=f"{err}") from err
