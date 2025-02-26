import logging
from contextlib import suppress

from aiohttp import web
from models_library.api_schemas_webserver.users import (
    MyProfileGet,
    MyProfilePatch,
    UserGet,
    UsersForAdminSearchQueryParams,
    UsersSearch,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_service_webserver.products._models import Product
from simcore_service_webserver.products._service import get_current_product

from .._meta import API_VTAG
from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..groups import api as groups_api
from ..groups.exceptions import GroupNotFoundError
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _users_service
from ._common.schemas import PreRegisteredUserGet, UsersRequestContext
from .exceptions import (
    AlreadyPreRegisteredError,
    MissingGroupExtraPropertiesForProductError,
    UserNameDuplicateError,
    UserNotFoundError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    UserNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        "This user cannot be found. Either it is not registered or has enabled privacy settings.",
    ),
    UserNameDuplicateError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Username '{user_name}' is already taken. "
        "Consider '{alternative_user_name}' instead.",
    ),
    AlreadyPreRegisteredError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        "Found {num_found} matches for '{email}'. Cannot pre-register existing user",
    ),
    MissingGroupExtraPropertiesForProductError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "The product is not ready for use until the configuration is fully completed. "
        "Please wait and try again. "
        "If this issue persists, contact support indicating this support code: {error_code}.",
    ),
}

_handle_users_exceptions = exception_handling_decorator(
    # Transforms raised service exceptions into controller-errors (i.e. http 4XX,5XX responses)
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
)


routes = web.RouteTableDef()

#
# MY PROFILE: /me
#


@routes.get(f"/{API_VTAG}/me", name="get_my_profile")
@login_required
@_handle_users_exceptions
async def get_my_profile(request: web.Request) -> web.Response:
    product: Product = get_current_product(request)
    req_ctx = UsersRequestContext.model_validate(request)

    groups_by_type = await groups_api.list_user_groups_with_read_access(
        request.app, user_id=req_ctx.user_id
    )

    assert groups_by_type.primary
    assert groups_by_type.everyone

    my_product_group = None

    if product.group_id:
        with suppress(GroupNotFoundError):
            # Product is optional
            my_product_group = await groups_api.get_product_group_for_user(
                app=request.app,
                user_id=req_ctx.user_id,
                product_gid=product.group_id,
            )

    my_profile, preferences = await _users_service.get_my_profile(
        request.app, user_id=req_ctx.user_id, product_name=req_ctx.product_name
    )

    profile = MyProfileGet.from_domain_model(
        my_profile, groups_by_type, my_product_group, preferences
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

    await _users_service.update_my_profile(
        request.app, user_id=req_ctx.user_id, update=profile_update
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# USERS (public)
#


@routes.post(f"/{API_VTAG}/users:search", name="search_users")
@login_required
@permission_required("user.read")
@_handle_users_exceptions
async def search_users(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    # NOTE: Decided for body instead of query parameters because it is easier for the front-end
    search_params = await parse_request_body_as(UsersSearch, request)

    found = await _users_service.search_public_users(
        request.app,
        caller_id=req_ctx.user_id,
        match_=search_params.match_,
        limit=search_params.limit,
    )

    return envelope_json_response([UserGet.from_domain_model(user) for user in found])


#
# USERS (only POs)
#

_RESPONSE_MODEL_MINIMAL_POLICY = RESPONSE_MODEL_POLICY.copy()
_RESPONSE_MODEL_MINIMAL_POLICY["exclude_none"] = True


@routes.get(f"/{API_VTAG}/admin/users:search", name="search_users_for_admin")
@login_required
@permission_required("admin.users.read")
@_handle_users_exceptions
async def search_users_for_admin(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    query_params: UsersForAdminSearchQueryParams = parse_request_query_parameters_as(
        UsersForAdminSearchQueryParams, request
    )

    found = await _users_service.search_users(
        request.app, email_glob=query_params.email, include_products=True
    )

    return envelope_json_response(
        [_.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY) for _ in found]
    )


@routes.post(
    f"/{API_VTAG}/admin/users:pre-register", name="pre_register_user_for_admin"
)
@login_required
@permission_required("admin.users.read")
@_handle_users_exceptions
async def pre_register_user_for_admin(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    pre_user_profile = await parse_request_body_as(PreRegisteredUserGet, request)

    user_profile = await _users_service.pre_register_user(
        request.app, profile=pre_user_profile, creator_user_id=req_ctx.user_id
    )
    return envelope_json_response(
        user_profile.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY)
    )
