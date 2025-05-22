import logging
from contextlib import suppress
from typing import Any

from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.api_schemas_webserver.users import (
    MyProfileGet,
    MyProfilePatch,
    UserAccountApprove,
    UserAccountGet,
    UserAccountReject,
    UserAccountSearchQueryParams,
    UserGet,
    UsersAccountListQueryParams,
    UsersSearch,
)
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

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
from ..products import products_web
from ..products.models import Product
from ..security.decorators import permission_required
from ..utils_aiohttp import create_json_response_from_page, envelope_json_response
from . import _users_service
from ._common.schemas import PreRegisteredUserGet, UsersRequestContext
from .exceptions import (
    AlreadyPreRegisteredError,
    MissingGroupExtraPropertiesForProductError,
    PendingPreRegistrationNotFoundError,
    UserNameDuplicateError,
    UserNotFoundError,
)

_logger = logging.getLogger(__name__)


_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    PendingPreRegistrationNotFoundError: HttpErrorInfo(
        status.HTTP_400_BAD_REQUEST,
        PendingPreRegistrationNotFoundError.msg_template,
    ),
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
        "Please wait and try again. ",
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
    product: Product = products_web.get_current_product(request)
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


@routes.get(f"/{API_VTAG}/admin/user-accounts", name="list_users_accounts")
@login_required
@permission_required("admin.users.read")
@_handle_users_exceptions
async def list_users_accounts(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    query_params = parse_request_query_parameters_as(
        UsersAccountListQueryParams, request
    )

    if query_params.review_status == "PENDING":
        filter_any_account_request_status = [AccountRequestStatus.PENDING]
    elif query_params.review_status == "REVIEWED":
        filter_any_account_request_status = [
            AccountRequestStatus.APPROVED,
            AccountRequestStatus.REJECTED,
        ]
    else:
        # ALL
        filter_any_account_request_status = None

    users, total_count = await _users_service.list_all_users_as_admin(
        request.app,
        product_name=req_ctx.product_name,
        filter_any_account_request_status=filter_any_account_request_status,
        pagination_limit=query_params.limit,
        pagination_offset=query_params.offset,
    )

    def _to_domain_model(user: dict[str, Any]) -> UserAccountGet:
        return UserAccountGet(
            extras=user.pop("extras") or {}, pre_registration_id=user.pop("id"), **user
        )

    page = Page[UserAccountGet].model_validate(
        paginate_data(
            chunk=[_to_domain_model(user) for user in users],
            request_url=request.url,
            total=total_count,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )

    return create_json_response_from_page(page)


@routes.get(f"/{API_VTAG}/admin/user-accounts:search", name="search_user_accounts")
@login_required
@permission_required("admin.users.read")
@_handle_users_exceptions
async def search_user_accounts(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    query_params: UserAccountSearchQueryParams = parse_request_query_parameters_as(
        UserAccountSearchQueryParams, request
    )

    found = await _users_service.search_users_as_admin(
        request.app, email_glob=query_params.email, include_products=True
    )

    return envelope_json_response(
        [
            user_for_admin.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY)
            for user_for_admin in found
        ]
    )


@routes.post(
    f"/{API_VTAG}/admin/user-accounts:pre-register", name="pre_register_user_account"
)
@login_required
@permission_required("admin.users.write")
@_handle_users_exceptions
async def pre_register_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    pre_user_profile = await parse_request_body_as(PreRegisteredUserGet, request)

    user_profile = await _users_service.pre_register_user(
        request.app,
        profile=pre_user_profile,
        creator_user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(
        user_profile.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY)
    )


@routes.post(f"/{API_VTAG}/admin/user-accounts:approve", name="approve_user_account")
@login_required
@permission_required("admin.users.write")
@_handle_users_exceptions
async def approve_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    approval_data = await parse_request_body_as(UserAccountApprove, request)

    if approval_data.invitation:
        _logger.debug(
            "TODO: User is being approved with invitation %s: \n"
            "1. Approve user account\n"
            "2. Generate invitation\n"
            "3. Store invitation in extras\n"
            "4. Send invitation to user %s\n",
            approval_data.invitation.model_dump_json(indent=1),
            approval_data.email,
        )

    # Approve the user account, passing the current user's ID as the reviewer
    pre_registration_id = await _users_service.approve_user_account(
        request.app,
        pre_registration_email=approval_data.email,
        product_name=req_ctx.product_name,
        reviewer_id=req_ctx.user_id,
    )
    assert pre_registration_id  # nosec

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{API_VTAG}/admin/user-accounts:reject", name="reject_user_account")
@login_required
@permission_required("admin.users.write")
@_handle_users_exceptions
async def reject_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    rejection_data = await parse_request_body_as(UserAccountReject, request)

    # Reject the user account, passing the current user's ID as the reviewer
    pre_registration_id = await _users_service.reject_user_account(
        request.app,
        pre_registration_email=rejection_data.email,
        product_name=req_ctx.product_name,
        reviewer_id=req_ctx.user_id,
    )
    assert pre_registration_id  # nosec

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
