import logging
from typing import Any

from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.api_schemas_invitations.invitations import ApiInvitationInputs
from models_library.api_schemas_webserver.users import (
    UserAccountApprove,
    UserAccountGet,
    UserAccountReject,
    UserAccountSearchQueryParams,
    UsersAccountListQueryParams,
)
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.logging_utils import log_context
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from servicelib.utils import fire_and_forget_task

from ...._meta import API_VTAG
from ....invitations import api as invitations_service
from ....login.decorators import login_required
from ....security.decorators import permission_required
from ....utils_aiohttp import create_json_response_from_page, envelope_json_response
from ... import _accounts_service
from ._rest_exceptions import handle_rest_requests_exceptions
from ._rest_schemas import PreRegisteredUserGet, UsersRequestContext

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()

_RESPONSE_MODEL_MINIMAL_POLICY = RESPONSE_MODEL_POLICY.copy()
_RESPONSE_MODEL_MINIMAL_POLICY["exclude_none"] = True


@routes.get(f"/{API_VTAG}/admin/user-accounts", name="list_users_accounts")
@login_required
@permission_required("admin.users.read")
@handle_rest_requests_exceptions
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

    users, total_count = await _accounts_service.list_user_accounts(
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
@handle_rest_requests_exceptions
async def search_user_accounts(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    query_params: UserAccountSearchQueryParams = parse_request_query_parameters_as(
        UserAccountSearchQueryParams, request
    )

    found = await _accounts_service.search_users_accounts(
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
@handle_rest_requests_exceptions
async def pre_register_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    pre_user_profile = await parse_request_body_as(PreRegisteredUserGet, request)

    user_profile = await _accounts_service.pre_register_user(
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
@handle_rest_requests_exceptions
async def approve_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    approval_data = await parse_request_body_as(UserAccountApprove, request)

    invitation_result = None
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

    # Approve the user account, passing the current user's ID as the reviewer
    pre_registration_id = await _accounts_service.approve_user_account(
        request.app,
        pre_registration_email=approval_data.email,
        product_name=req_ctx.product_name,
        reviewer_id=req_ctx.user_id,
        invitation_extras=(
            {"invitation": invitation_result.model_dump(mode="json")}
            if invitation_result
            else None
        ),
    )
    assert pre_registration_id  # nosec

    if invitation_result:
        with log_context(
            _logger,
            logging.INFO,
            "Sending invitation email to %s ...",
            approval_data.email,
        ):
            # get pre-registration data
            found = await _accounts_service.search_users_accounts(
                request.app,
                email_glob=approval_data.email,
                product_name=req_ctx.product_name,
                include_products=False,
            )
            user_account = found[0]
            assert user_account.pre_registration_id == pre_registration_id  # nosec
            assert user_account.email == approval_data.email  # nosec

            # send email to user
            fire_and_forget_task(
                _accounts_service.send_approval_email_to_user(
                    request.app,
                    product_name=req_ctx.product_name,
                    invitation_link=invitation_result.invitation_url,
                    user_email=approval_data.email,
                    first_name=user_account.first_name or "User",
                    last_name=user_account.last_name or "",
                ),
                task_suffix_name=f"{__name__}.send_approval_email_to_user.{approval_data.email}",
                fire_and_forget_tasks_collection=request.app[
                    APP_FIRE_AND_FORGET_TASKS_KEY
                ],
            )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{API_VTAG}/admin/user-accounts:reject", name="reject_user_account")
@login_required
@permission_required("admin.users.write")
@handle_rest_requests_exceptions
async def reject_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    rejection_data = await parse_request_body_as(UserAccountReject, request)

    # Reject the user account, passing the current user's ID as the reviewer
    pre_registration_id = await _accounts_service.reject_user_account(
        request.app,
        pre_registration_email=rejection_data.email,
        product_name=req_ctx.product_name,
        reviewer_id=req_ctx.user_id,
    )
    assert pre_registration_id  # nosec

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
