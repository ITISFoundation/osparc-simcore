import logging

from aiohttp import web
from servicelib.aiohttp.rest_utils import extract_and_validate
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON

from ..products import Product, get_current_product
from ..security_api import check_password, encrypt_password
from ..utils import HOUR
from ..utils_rate_limiting import global_rate_limit_route
from ._confirmation import is_confirmation_allowed, make_confirmation_link
from .decorators import RQT_USERID_KEY, login_required
from .settings import LoginOptions, get_plugin_options
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import (
    ACTIVE,
    CHANGE_EMAIL,
    RESET_PASSWORD,
    flash_response,
    validate_user_status,
)
from .utils_email import get_template_path, render_and_send_mail

log = logging.getLogger(__name__)


@global_rate_limit_route(number_of_requests=10, interval_seconds=HOUR)
async def reset_password(request: web.Request):
    """
        1. confirm user exists
        2. check user status
        3. send email with link to reset password
        4. user clicks confirmation link -> auth/confirmation/{} -> reset_password_allowed

    Follows guidelines from [1]: https://postmarkapp.com/guides/password-reset-email-best-practices
     - You would never want to confirm or deny the existence of an account with a given email or username.
     - Expiration of link
     - Support contact information
     - Who requested the reset?
    """
    _, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    email = body.email

    user = await db.get_user({"email": email})
    try:
        if not user:
            raise web.HTTPUnprocessableEntity(
                reason=cfg.MSG_UNKNOWN_EMAIL, content_type=MIMETYPE_APPLICATION_JSON
            )  # 422

        validate_user_status(user, cfg, product.support_email)

        assert user["status"] == ACTIVE  # nosec
        assert user["email"] == email  # nosec

        if not await is_confirmation_allowed(cfg, db, user, action=RESET_PASSWORD):
            raise web.HTTPUnauthorized(
                reason=cfg.MSG_OFTEN_RESET_PASSWORD,
                content_type=MIMETYPE_APPLICATION_JSON,
            )  # 401

    except web.HTTPError as err:
        try:
            await render_and_send_mail(
                request,
                from_=product.support_email,
                to=email,
                template=await get_template_path(
                    request, "reset_password_email_failed.jinja2"
                ),
                context={
                    "host": request.host,
                    "reason": err.reason,
                },
            )
        except Exception as err_mail:  # pylint: disable=broad-except
            log.exception("Cannot send email")
            raise web.HTTPServiceUnavailable(
                reason=cfg.MSG_CANT_SEND_MAIL
            ) from err_mail
    else:
        confirmation = await db.create_confirmation(user["id"], action=RESET_PASSWORD)
        link = make_confirmation_link(request, confirmation)
        try:
            # primary reset email with a URL and the normal instructions.
            await render_and_send_mail(
                request,
                from_=product.support_email,
                to=email,
                template=await get_template_path(
                    request, "reset_password_email.jinja2"
                ),
                context={
                    "host": request.host,
                    "link": link,
                },
            )
        except Exception as err:  # pylint: disable=broad-except
            log.exception("Can not send email")
            await db.delete_confirmation(confirmation)
            raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL) from err

    response = flash_response(cfg.MSG_EMAIL_SENT.format(email=email), "INFO")
    return response


@login_required
async def change_email(request: web.Request):
    _, _, body = await extract_and_validate(request)

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    email = body.email

    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    assert user  # nosec

    if user["email"] == email:
        return flash_response("Email changed")

    other = await db.get_user({"email": email})
    if other:
        raise web.HTTPUnprocessableEntity(reason="This email cannot be used")

    # Reset if previously requested
    confirmation = await db.get_confirmation({"user": user, "action": CHANGE_EMAIL})
    if confirmation:
        await db.delete_confirmation(confirmation)

    # create new confirmation to ensure email is actually valid
    confirmation = await db.create_confirmation(user["id"], CHANGE_EMAIL, email)
    link = make_confirmation_link(request, confirmation)
    try:
        await render_and_send_mail(
            request,
            from_=product.support_email,
            to=email,
            template=await get_template_path(request, "change_email_email.jinja2"),
            context={
                "host": request.host,
                "link": link,
            },
        )
    except Exception as err:  # pylint: disable=broad-except
        log.error("Can not send email")
        await db.delete_confirmation(confirmation)
        raise web.HTTPServiceUnavailable(reason=cfg.MSG_CANT_SEND_MAIL) from err

    response = flash_response(cfg.MSG_CHANGE_EMAIL_REQUESTED)
    return response


@login_required
async def change_password(request: web.Request):

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)

    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    assert user  # nosec

    _, _, body = await extract_and_validate(request)

    cur_password = body.current
    new_password = body.new
    confirm = body.confirm

    if not check_password(cur_password, user["password_hash"]):
        raise web.HTTPUnprocessableEntity(
            reason=cfg.MSG_WRONG_PASSWORD, content_type=MIMETYPE_APPLICATION_JSON
        )  # 422

    if new_password != confirm:
        raise web.HTTPConflict(
            reason=cfg.MSG_PASSWORD_MISMATCH, content_type=MIMETYPE_APPLICATION_JSON
        )  # 409

    await db.update_user(user, {"password_hash": encrypt_password(new_password)})

    response = flash_response(cfg.MSG_PASSWORD_CHANGED)
    return response
