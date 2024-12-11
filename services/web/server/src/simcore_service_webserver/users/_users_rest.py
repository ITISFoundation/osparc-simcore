import functools
import logging

from aiohttp import web
from models_library.api_schemas_webserver.users import (
    MyProfileGet,
    MyProfilePatch,
    UsersSearchQueryParams,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _users_service, api
from .common._constants import FMSG_MISSING_CONFIG_WITH_OEC
from .common._schemas import PreRegisteredUserGet, UsersRequestContext
from .exceptions import (
    AlreadyPreRegisteredError,
    MissingGroupExtraPropertiesForProductError,
    UserNameDuplicateError,
    UserNotFoundError,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


def _handle_users_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except UserNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except UserNameDuplicateError as exc:
            raise web.HTTPConflict(reason=f"{exc}") from exc

        except MissingGroupExtraPropertiesForProductError as exc:
            error_code = exc.error_code()
            user_error_msg = FMSG_MISSING_CONFIG_WITH_OEC.format(error_code=error_code)
            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    user_error_msg,
                    error=exc,
                    error_code=error_code,
                    tip="Row in `groups_extra_properties` for this product is missing.",
                )
            )
            raise web.HTTPServiceUnavailable(reason=user_error_msg) from exc

    return wrapper


@routes.get(f"/{API_VTAG}/me", name="get_my_profile")
@login_required
@_handle_users_exceptions
async def get_my_profile(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)

    profile: MyProfileGet = await api.get_user_profile(
        request.app, user_id=req_ctx.user_id, product_name=req_ctx.product_name
    )

    return envelope_json_response(profile)


@routes.patch(f"/{API_VTAG}/me", name="update_my_profile")
@routes.put(
    f"/{API_VTAG}/me", name="replace_my_profile"  # deprecated. Use patch instead
)
@login_required
@permission_required("user.profile.update")
@_handle_users_exceptions
async def update_my_profile(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    profile_update = await parse_request_body_as(MyProfilePatch, request)

    await api.update_user_profile(
        request.app, user_id=req_ctx.user_id, update=profile_update
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


_RESPONSE_MODEL_MINIMAL_POLICY = RESPONSE_MODEL_POLICY.copy()
_RESPONSE_MODEL_MINIMAL_POLICY["exclude_none"] = True


@routes.get(f"/{API_VTAG}/users:search", name="search_users")
@login_required
@permission_required("user.users.*")
@_handle_users_exceptions
async def search_users(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    query_params: UsersSearchQueryParams = parse_request_query_parameters_as(
        UsersSearchQueryParams, request
    )

    found = await _users_service.search_users(
        request.app, email_glob=query_params.email, include_products=True
    )

    return envelope_json_response(
        [_.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY) for _ in found]
    )


@routes.post(f"/{API_VTAG}/users:pre-register", name="pre_register_user")
@login_required
@permission_required("user.users.*")
@_handle_users_exceptions
async def pre_register_user(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    pre_user_profile = await parse_request_body_as(PreRegisteredUserGet, request)

    try:
        user_profile = await _users_service.pre_register_user(
            request.app, profile=pre_user_profile, creator_user_id=req_ctx.user_id
        )
        return envelope_json_response(
            user_profile.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY)
        )
    except AlreadyPreRegisteredError as err:
        raise web.HTTPConflict(reason=f"{err}") from err
