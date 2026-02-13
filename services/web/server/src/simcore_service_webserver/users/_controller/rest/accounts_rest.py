import logging
from typing import Any

from aiohttp import web
from common_library.users_enums import AccountRequestStatus
from models_library.api_schemas_invitations.invitations import ApiInvitationInputs
from models_library.api_schemas_webserver.notifications import MessageContentGet
from models_library.api_schemas_webserver.users import (
    UserAccountApprove,
    UserAccountGet,
    UserAccountPreviewApproval,
    UserAccountPreviewApprovalGet,
    UserAccountPreviewRejection,
    UserAccountPreviewRejectionGet,
    UserAccountReject,
    UserAccountSearchQueryParams,
    UsersAccountListQueryParams,
)
from models_library.notifications import ChannelType, TemplateRef
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_query_parameters_as,
)
from servicelib.logging_utils import log_context
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from ...._meta import API_VTAG
from ....invitations import api as invitations_service
from ....login.decorators import login_required
from ....notifications import notifications_service
from ....notifications._models import EmailContact
from ....security.decorators import (
    group_or_role_permission_required,
    permission_required,
)
from ....utils_aiohttp import create_json_response_from_page, envelope_json_response
from ... import _accounts_service
from ._rest_exceptions import handle_rest_requests_exceptions
from ._rest_schemas import UserAccountRestPreRegister, UsersRequestContext

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()

_RESPONSE_MODEL_MINIMAL_POLICY = RESPONSE_MODEL_POLICY.copy()
_RESPONSE_MODEL_MINIMAL_POLICY["exclude_none"] = True


@routes.get(f"/{API_VTAG}/admin/user-accounts", name="list_users_accounts")
@login_required
@group_or_role_permission_required("admin.users.read")
@handle_rest_requests_exceptions
async def list_users_accounts(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    query_params = parse_request_query_parameters_as(UsersAccountListQueryParams, request)

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

    user_accounts, total_count = await _accounts_service.list_user_accounts(
        request.app,
        product_name=req_ctx.product_name,
        filter_any_account_request_status=filter_any_account_request_status,
        pagination_limit=query_params.limit,
        pagination_offset=query_params.offset,
    )

    def _to_domain_model(account_details: dict[str, Any]) -> UserAccountGet:
        account_details.pop("account_request_reviewed_by", None)
        return UserAccountGet(
            extras=account_details.pop("extras") or {},
            pre_registration_id=account_details.pop("id"),
            pre_registration_created=account_details.pop("created"),
            account_request_reviewed_by=account_details.pop("account_request_reviewed_by_username"),
            **account_details,
        )

    page = Page[UserAccountGet].model_validate(
        paginate_data(
            chunk=[_to_domain_model(user) for user in user_accounts],
            request_url=request.url,
            total=total_count,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )

    return create_json_response_from_page(page)


@routes.get(f"/{API_VTAG}/admin/user-accounts:search", name="search_user_accounts")
@login_required
@group_or_role_permission_required("admin.users.read")
@handle_rest_requests_exceptions
async def search_user_accounts(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    query_params: UserAccountSearchQueryParams = parse_request_query_parameters_as(
        UserAccountSearchQueryParams, request
    )

    found = await _accounts_service.search_users_accounts(
        request.app,
        filter_by_email_glob=query_params.email,
        filter_by_primary_group_id=query_params.primary_group_id,
        filter_by_user_name_glob=query_params.user_name,
        include_products=True,
    )

    return envelope_json_response(
        [user_for_admin.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY) for user_for_admin in found]
    )


@routes.post(f"/{API_VTAG}/admin/user-accounts:pre-register", name="pre_register_user_account")
@login_required
@permission_required("admin.users.write")
@handle_rest_requests_exceptions
async def pre_register_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    pre_user_profile = await parse_request_body_as(UserAccountRestPreRegister, request)

    user_profile = await _accounts_service.pre_register_user(
        request.app,
        profile=pre_user_profile,
        creator_user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(user_profile.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY))


@routes.post(f"/{API_VTAG}/admin/user-accounts:approve", name="approve_user_account")
@login_required
@permission_required("admin.users.write")
@handle_rest_requests_exceptions
async def approve_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    approval_data = await parse_request_body_as(UserAccountApprove, request)

    invitation_result = await invitations_service.extract_invitation(
        request.app,
        f"{approval_data.invitation_url}",
    )

    # Approve the user account, passing the current user's ID as the reviewer
    pre_registration_id = await _accounts_service.approve_user_account(
        request.app,
        pre_registration_email=approval_data.email,
        product_name=req_ctx.product_name,
        reviewer_id=req_ctx.user_id,
        invitation_extras=({"invitation": invitation_result.model_dump(mode="json")} if invitation_result else None),
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
                filter_by_email_glob=approval_data.email,
                product_name=req_ctx.product_name,
                include_products=False,
            )
            user_account = found[0]
            assert user_account.pre_registration_id == pre_registration_id  # nosec
            assert user_account.email == approval_data.email  # nosec

            # send email to user
            if approval_data.message_content:
                await notifications_service.send_message(
                    request.app,
                    user_id=req_ctx.user_id,
                    product_name=req_ctx.product_name,
                    channel=ChannelType.email,
                    group_ids=None,
                    external_contacts=[EmailContact(email=approval_data.email)],
                    content=approval_data.message_content.model_dump(),
                )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{API_VTAG}/admin/user-accounts:preview-approval", name="preview_approval_user_account")
@login_required
@permission_required("admin.users.read")
@handle_rest_requests_exceptions
async def preview_approval_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    approval_data = await parse_request_body_as(UserAccountPreviewApproval, request)

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
            product=req_ctx.product_name,
        )

        invitation_result = await invitations_service.generate_invitation(
            request.app,
            params=invitation_params,
            product_origin_url=request.url.origin(),
        )

        assert (  # nosec
            invitation_result.extra_credits_in_usd == approval_data.invitation.extra_credits_in_usd
        )
        assert (  # nosec
            invitation_result.trial_account_days == approval_data.invitation.trial_account_days
        )
        assert invitation_result.guest == approval_data.email  # nosec

        invitation_url = invitation_result.invitation_url

        # get pre-registration data
    found = await _accounts_service.search_users_accounts(
        request.app,
        filter_by_email_glob=approval_data.email,
        product_name=req_ctx.product_name,
        include_products=False,
    )
    user_account = found[0]
    assert user_account.email == approval_data.email  # nosec

    preview = await notifications_service.preview_template(
        app=request.app,
        product_name=req_ctx.product_name,
        ref=TemplateRef(
            channel=ChannelType.email,
            template_name="account_approved",
        ),
        context={
            "user": {
                "first_name": user_account.first_name,
            },
            "link": invitation_url,
            "trial_account_days": approval_data.invitation.trial_account_days,
            "extra_credits_in_usd": approval_data.invitation.extra_credits_in_usd,
        },
    )

    response = UserAccountPreviewApprovalGet(
        invitation_url=invitation_url,
        message_content=TypeAdapter(MessageContentGet).validate_python(preview.message_content),
    )

    return envelope_json_response(response.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY))


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

    # send email to user
    if rejection_data.message_content:
        await notifications_service.send_message(
            request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            channel=ChannelType.email,
            group_ids=None,
            external_contacts=[EmailContact(email=rejection_data.email)],
            content=rejection_data.message_content.model_dump(),
        )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{API_VTAG}/admin/user-accounts:preview-rejection", name="preview_rejection_user_account")
@login_required
@permission_required("admin.users.write")
@handle_rest_requests_exceptions
async def preview_rejection_user_account(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    rejection_data = await parse_request_body_as(UserAccountPreviewRejection, request)
    found = await _accounts_service.search_users_accounts(
        request.app,
        filter_by_email_glob=rejection_data.email,
        product_name=req_ctx.product_name,
        include_products=False,
    )
    user_account = found[0]
    assert user_account.email == rejection_data.email  # nosec

    preview = await notifications_service.preview_template(
        app=request.app,
        product_name=req_ctx.product_name,
        ref=TemplateRef(
            channel=ChannelType.email,
            template_name="account_rejected",
        ),
        context={
            "user": {
                "first_name": user_account.first_name,
            },
        },
    )

    response = UserAccountPreviewRejectionGet(
        message_content=TypeAdapter(MessageContentGet).validate_python(preview.message_content),
    )

    return envelope_json_response(response.model_dump(**_RESPONSE_MODEL_MINIMAL_POLICY))
