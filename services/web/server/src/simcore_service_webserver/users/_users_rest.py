import logging
from contextlib import suppress
from typing import Any

from aiohttp import web
from common_library.user_messages import user_message
from common_library.users_enums import AccountRequestStatus
from models_library.api_schemas_invitations.invitations import ApiInvitationInputs
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
from servicelib.logging_utils import log_context
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from servicelib.tracing import with_profiled_span

from .._meta import API_VTAG
from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..groups import api as groups_api
from ..groups.exceptions import GroupNotFoundError
from ..invitations import api as invitations_service
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
        user_message(
            "No pending registration request found for email {email} in {product_name}.",
            _version=2,
        ),
    ),
    UserNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message(
            "The requested user could not be found. "
            "This may be because the user is not registered or has privacy settings enabled.",
            _version=1,
        ),
    ),
    UserNameDuplicateError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "The username '{user_name}' is already in use. "
            "Please try '{alternative_user_name}' instead.",
            _version=1,
        ),
    ),
    AlreadyPreRegisteredError: HttpErrorInfo(
        status.HTTP_409_CONFLICT,
        user_message(
            "Found {num_found} existing account(s) for '{email}'. Unable to pre-register an existing user.",
            _version=1,
        ),
    ),
    MissingGroupExtraPropertiesForProductError: HttpErrorInfo(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        user_message(
            "This product is currently being configured and is not yet ready for use. "
            "Please try again later.",
            _version=1,
        ),
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
@with_profiled_span
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

    users, total_count = await _users_service.list_user_accounts(
        request.app,
        product_name=req_ctx.product_name,
        filter_any_account_request_status=filter_any_account_request_status,
        pagination_limit=query_params.limit,
        pagination_offset=query_params.offset,
    )

    def _to_domain_model(user: dict[str, Any]) -> UserAccountGet:
        return UserAccountGet(
            extras=user.pop("extras") or {},
            pre_registration_id=user.pop("id"),
            pre_registration_created=user.pop("created"),
            **user,
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

    found = await _users_service.search_users_accounts(
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

    invitation_extras = None
    if approval_data.invitation:
        with log_context(
            _logger,
            logging.DEBUG,
            "User is being approved with invitation %s for user %s",
            approval_data.invitation.model_dump_json(indent=1),
            approval_data.email,
        ):
            # Generate invitation
            invitation_params = ApiInvitationInputs(
                issuer=str(req_ctx.user_id),
                guest=approval_data.email,
                trial_account_days=approval_data.invitation.trial_account_days,
                extra_credits_in_usd=approval_data.invitation.extra_credits_in_usd,
            )

            invitation_result = await invitations_service.generate_invitation(
                request.app, params=invitation_params
            )

            assert (  # nosec
                invitation_result.extra_credits_in_usd
                == approval_data.invitation.extra_credits_in_usd
            )
            assert (  # nosec
                invitation_result.trial_account_days
                == approval_data.invitation.trial_account_days
            )
            assert invitation_result.guest == approval_data.email  # nosec

            # Store invitation data in extras
            invitation_extras = {
                "invitation": invitation_result.model_dump(mode="json")
            }

    # Approve the user account, passing the current user's ID as the reviewer
    pre_registration_id = await _users_service.approve_user_account(
        request.app,
        pre_registration_email=approval_data.email,
        product_name=req_ctx.product_name,
        reviewer_id=req_ctx.user_id,
        invitation_extras=invitation_extras,
    )
    assert pre_registration_id  # nosec

    if invitation_extras:
        _logger.debug(
            "Sending invitation email for user %s [STILL MISSING]", approval_data.email
        )

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
