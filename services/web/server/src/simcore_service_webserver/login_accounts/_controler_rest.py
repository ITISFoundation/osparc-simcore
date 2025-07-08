import logging
from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.auth import (
    AccountRequestInfo,
    UnregisterCheck,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.utils import fire_and_forget_task

from .._meta import API_VTAG
from ..login import login_service
from ..login.constants import (
    CAPTCHA_SESSION_KEY,
    MSG_LOGGED_OUT,
    MSG_WRONG_CAPTCHA__INVALID,
)
from ..login.settings import get_plugin_settings
from ..login_auth.decorators import login_required
from ..models import AuthenticatedRequestContext
from ..products import products_web
from ..products.models import Product
from ..security import security_service, security_web
from ..security.decorators import permission_required
from ..session import api as session_service
from ..users import api as users_service
from ..users._common.schemas import PreRegisteredUserGet
from ..utils import MINUTE
from ..utils_rate_limiting import global_rate_limit_route
from ..web_utils import flash_response
from . import _service
from ._controller._rest_exceptions import handle_rest_requests_exceptions

_logger = logging.getLogger(__name__)


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


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/auth/captcha", name="create_captcha")
@global_rate_limit_route(number_of_requests=30, interval_seconds=MINUTE)
@handle_rest_requests_exceptions
async def create_captcha(request: web.Request):
    session = await session_service.get_session(request)

    captcha_text, image_data = await _service.create_captcha()

    # Store captcha text in session
    session[CAPTCHA_SESSION_KEY] = captcha_text

    return web.Response(body=image_data, content_type="image/png")


@routes.post(
    f"/{API_VTAG}/auth/request-account",
    name="request_product_account",
)
@global_rate_limit_route(number_of_requests=30, interval_seconds=MINUTE)
@handle_rest_requests_exceptions
async def request_product_account(request: web.Request):
    product = products_web.get_current_product(request)
    session = await session_service.get_session(request)

    body = await parse_request_body_as(AccountRequestInfo, request)
    assert body.form  # nosec
    assert body.captcha  # nosec

    if body.captcha != session.get(CAPTCHA_SESSION_KEY):
        raise web.HTTPUnprocessableEntity(text=MSG_WRONG_CAPTCHA__INVALID)
    session.pop(CAPTCHA_SESSION_KEY, None)

    # create pre-regiatration or raise if already exists
    await _service.create_pre_registration(
        request.app,
        profile=PreRegisteredUserGet.model_validate(body.form),
        product_name=product.name,
    )

    # if created send email to fogbugz or user itself
    fire_and_forget_task(
        _service.send_account_request_email_to_support(
            request=request,
            product=product,
            request_form=body.form,
            ipinfo=_get_ipinfo(request),
        ),
        task_suffix_name=f"{__name__}.request_product_account.send_account_request_email_to_support",
        fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.post(f"/{API_VTAG}/auth/unregister", name="unregister_account")
@login_required
@permission_required("user.profile.delete")
@handle_rest_requests_exceptions
async def unregister_account(request: web.Request):
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    body = await parse_request_body_as(UnregisterCheck, request)

    product: Product = products_web.get_current_product(request)
    settings = get_plugin_settings(request.app, product_name=product.name)

    # checks before deleting
    credentials = await users_service.get_user_credentials(
        request.app, user_id=req_ctx.user_id
    )
    if body.email != credentials.email.lower() or not security_service.check_password(
        body.password.get_secret_value(), credentials.password_hash
    ):
        raise web.HTTPConflict(
            text="Wrong email or password. Please try again to delete this account"
        )

    with log_context(
        _logger,
        logging.INFO,
        "Mark account for deletion to %s",
        credentials.email,
        extra=get_log_record_extra(user_id=req_ctx.user_id),
    ):
        # update user table
        await users_service.set_user_as_deleted(request.app, user_id=req_ctx.user_id)

        # logout
        await login_service.notify_user_logout(
            request.app, user_id=req_ctx.user_id, client_session_id=None
        )
        response = flash_response(MSG_LOGGED_OUT, "INFO")
        await security_web.forget_identity(request, response)

        # send email in the background
        fire_and_forget_task(
            _service.send_close_account_email(
                request,
                user_email=credentials.email,
                user_first_name=credentials.display_name,
                retention_days=settings.LOGIN_ACCOUNT_DELETION_RETENTION_DAYS,
            ),
            task_suffix_name=f"{__name__}.unregister_account.send_close_account_email",
            fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )

        return response
