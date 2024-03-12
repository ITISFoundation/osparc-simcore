import logging
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.auth import (
    AccountRequestInfo,
    UnregisterCheck,
)
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.utils import fire_and_forget_task

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG
from ..products.api import get_current_product
from ..security.api import check_password, forget_identity
from ..security.decorators import permission_required
from ..users.api import get_user_credentials, set_user_as_deleted
from ..utils import MINUTE
from ..utils_rate_limiting import global_rate_limit_route
from ._constants import MSG_LOGGED_OUT
from ._registration_api import (
    send_account_request_email_to_support,
    send_close_account_email,
)
from .decorators import login_required
from .utils import flash_response, notify_user_logout

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


def _get_ipinfo(request: web.Request) -> dict[str, Any]:
    # NOTE:  Traefik is also configured to transmit the original IP.
    x_real_ip = request.headers.get("X-Real-IP", None)
    # SEE https://docs.aiohttp.org/en/stable/web_reference.html#aiohttp.web.BaseRequest.transport
    peername: tuple | None = (
        request.transport.get_extra_info("peername") if request.transport else None
    )
    return {
        "x-real-ip": x_real_ip,
        "x-forwarded-for": request.headers.get("X-Forwarded-For", None),
        "peername": peername,
        "test_url": f"https://ipinfo.io/{x_real_ip}/json",
    }


@routes.post(
    f"/{API_VTAG}/auth/request-account",
    name="request_product_account",
)
@global_rate_limit_route(number_of_requests=30, interval_seconds=MINUTE)
async def request_product_account(request: web.Request):
    product = get_current_product(request)
    body = await parse_request_body_as(AccountRequestInfo, request)
    assert body.form  # nosec

    # send email to fogbugz or user itself
    fire_and_forget_task(
        send_account_request_email_to_support(
            request,
            product=product,
            request_form=body.form,
            ipinfo=_get_ipinfo(request),
        ),
        task_suffix_name=f"{__name__}.request_product_account.send_account_request_email_to_support",
        fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )
    raise web.HTTPNoContent


class _AuthenticatedContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


@routes.post(f"/{API_VTAG}/auth/unregister", name="unregister_account")
@login_required
@permission_required("user.profile.delete")
async def unregister_account(request: web.Request):
    req_ctx = _AuthenticatedContext.parse_obj(request)
    body = await parse_request_body_as(UnregisterCheck, request)

    # checks before deleting
    credentials = await get_user_credentials(request.app, user_id=req_ctx.user_id)
    if body.email != credentials.email.lower() or not check_password(
        body.password.get_secret_value(), credentials.password_hash
    ):
        raise web.HTTPConflict(
            reason="Wrong email or password. Please try again to delete this account"
        )

    with log_context(
        _logger,
        logging.INFO,
        "Mark account for deletion to %s",
        credentials.email,
        extra=get_log_record_extra(user_id=req_ctx.user_id),
    ):
        # update user table
        await set_user_as_deleted(request.app, user_id=req_ctx.user_id)

        # logout
        await notify_user_logout(
            request.app, user_id=req_ctx.user_id, client_session_id=None
        )
        response = flash_response(MSG_LOGGED_OUT, "INFO")
        await forget_identity(request, response)

        # send email in the background
        fire_and_forget_task(
            send_close_account_email(
                request,
                user_email=credentials.email,
                user_name=credentials.display_name,
                retention_days=30,
            ),
            task_suffix_name=f"{__name__}.unregister_account.send_close_account_email",
            fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )

        return response
