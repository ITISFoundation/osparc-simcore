import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.emails import LowerCaseEmailStr
from pydantic import SecretStr, field_validator
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.utils_users import UsersRepo

from .._meta import API_VTAG
from ..db.plugin import get_database_engine
from ..products import products_web
from ..products.models import Product
from ..security.api import check_password, encrypt_password
from ..users import api as users_service
from ..utils import HOUR
from ..utils_rate_limiting import global_rate_limit_route
from ._confirmation import get_or_create_confirmation, make_confirmation_link
from ._constants import (
    MSG_CANT_SEND_MAIL,
    MSG_CHANGE_EMAIL_REQUESTED,
    MSG_EMAIL_SENT,
    MSG_OFTEN_RESET_PASSWORD,
    MSG_PASSWORD_CHANGED,
    MSG_WRONG_PASSWORD,
)
from ._models import InputSchema, create_password_match_validator
from .decorators import login_required
from .settings import LoginOptions, get_plugin_options
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import (
    ACTIVE,
    CHANGE_EMAIL,
    flash_response,
    validate_user_status,
)
from .utils_email import get_template_path, send_email_from_template

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


class ResetPasswordBody(InputSchema):
    email: LowerCaseEmailStr


@routes.post(f"/{API_VTAG}/auth/reset-password", name="initiate_reset_password")
@global_rate_limit_route(
    number_of_requests=10, interval_seconds=HOUR, error_msg=MSG_OFTEN_RESET_PASSWORD
)
async def initiate_reset_password(request: web.Request):
    """First of the "Two-Step Action Confirmation pattern": initiate_reset_password + complete_reset_password(code)

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

    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = products_web.get_current_product(request)

    request_body = await parse_request_body_as(ResetPasswordBody, request)

    _error_msg_prefix, _error_msg_suffix = (
        "Password reset initiated",
        "Ignoring request.",
    )

    def _get_error_context(
        user=None,
    ) -> dict[str, str]:
        ctx = {
            "user_email": request_body.email,
            "product_name": product.name,
            "request.remote": f"{request.remote}",
            "request.method": f"{request.method}",
            "request.path": f"{request.path}",
        }

        if user:
            ctx.update(
                {
                    "user_email": request_body.email,
                    "user_id": user["id"],
                    "user_status": user["status"],
                    "user_role": user["role"],
                }
            )
        return ctx

    ok = True

    # CHECK user exists
    user = await db.get_user({"email": request_body.email})
    if not user:
        _logger.warning(
            **create_troubleshotting_log_kwargs(
                f"{_error_msg_prefix} for non-existent email. {_error_msg_suffix}",
                error=Exception("No user found with this email"),
                error_context=_get_error_context(),
            )
        )
        ok = False

    if ok:
        assert user  # nosec
        assert user["email"] == request_body.email  # nosec

        # CHECK user state
        try:
            validate_user_status(user=dict(user), support_email=product.support_email)
        except web.HTTPError as err:
            # NOTE: we abuse here (untiby reusing `validate_user_status` and catching http errors that we
            # do not want to forward but rather log due to the special rules in this entrypoint
            _logger.warning(
                **create_troubleshotting_log_kwargs(
                    f"{_error_msg_prefix} for invalid user. {_error_msg_suffix}.",
                    error=err,
                    error_context=_get_error_context(user),
                )
            )
            ok = False

    if ok:
        assert user  # nosec
        assert user["status"] == ACTIVE  # nosec
        assert isinstance(user["id"], int)  # nosec

        # CHECK access to product
        if not await users_service.is_user_in_product(
            request.app, user_id=user["id"], product_name=product.name
        ):
            _logger.warning(
                **create_troubleshotting_log_kwargs(
                    f"{_error_msg_prefix} for a user with NO access to this product. {_error_msg_suffix}.",
                    error=Exception("User cannot access this product"),
                    error_context=_get_error_context(user),
                )
            )
            ok = False

    if ok:
        assert user  # nosec

        try:
            # confirmation token that includes code to complete_reset_password
            confirmation = await get_or_create_confirmation(
                cfg, db, user_id=user["id"], action="RESET_PASSWORD"
            )

            # Produce a link so that the front-end can hit `complete_reset_password`
            link = make_confirmation_link(request, confirmation)

            # primary reset email with a URL and the normal instructions.
            await send_email_from_template(
                request,
                from_=product.support_email,
                to=request_body.email,
                template=await get_template_path(
                    request, "reset_password_email.jinja2"
                ),
                context={
                    "name": user.get("first_name") or user["name"],
                    "host": request.host,
                    "link": link,
                    "product": product,
                },
            )
        except Exception as err:  # pylint: disable=broad-except
            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    "Unable to send email",
                    error=err,
                    error_context=_get_error_context(user),
                )
            )
            raise web.HTTPServiceUnavailable(reason=MSG_CANT_SEND_MAIL) from err

    # NOTE: Always same response: never want to confirm or deny the existence of an account
    # with a given email or username.
    return flash_response(MSG_EMAIL_SENT.format(email=request_body.email), "INFO")


class ChangeEmailBody(InputSchema):
    email: LowerCaseEmailStr


async def submit_request_to_change_email(request: web.Request):
    # NOTE: This code have been intentially disabled in https://github.com/ITISFoundation/osparc-simcore/pull/5472
    db: AsyncpgStorage = get_plugin_storage(request.app)
    product: Product = products_web.get_current_product(request)

    request_body = await parse_request_body_as(ChangeEmailBody, request)

    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    assert user  # nosec

    if user["email"] == request_body.email:
        return flash_response("Email changed")

    async with get_database_engine(request.app).acquire() as conn:
        if await UsersRepo.is_email_used(conn, email=request_body.email):
            raise web.HTTPUnprocessableEntity(reason="This email cannot be used")

    # Reset if previously requested
    confirmation = await db.get_confirmation({"user": user, "action": CHANGE_EMAIL})
    if confirmation:
        await db.delete_confirmation(confirmation)

    # create new confirmation to ensure email is actually valid
    confirmation = await db.create_confirmation(
        user_id=user["id"], action="CHANGE_EMAIL", data=request_body.email
    )
    link = make_confirmation_link(request, confirmation)
    try:
        await send_email_from_template(
            request,
            from_=product.support_email,
            to=request_body.email,
            template=await get_template_path(request, "change_email_email.jinja2"),
            context={
                "host": request.host,
                "link": link,
                "product": product,
            },
        )
    except Exception as err:  # pylint: disable=broad-except
        _logger.exception("Can not send change_email_email")
        await db.delete_confirmation(confirmation)
        raise web.HTTPServiceUnavailable(reason=MSG_CANT_SEND_MAIL) from err

    return flash_response(MSG_CHANGE_EMAIL_REQUESTED)


class ChangePasswordBody(InputSchema):
    current: SecretStr
    new: SecretStr
    confirm: SecretStr

    _password_confirm_match = field_validator("confirm")(
        create_password_match_validator(reference_field="new")
    )


@routes.post(f"/{API_VTAG}/auth/change-password", name="auth_change_password")
@login_required
async def change_password(request: web.Request):

    db: AsyncpgStorage = get_plugin_storage(request.app)
    passwords = await parse_request_body_as(ChangePasswordBody, request)

    user = await db.get_user({"id": request[RQT_USERID_KEY]})
    assert user  # nosec

    if not check_password(passwords.current.get_secret_value(), user["password_hash"]):
        raise web.HTTPUnprocessableEntity(
            reason=MSG_WRONG_PASSWORD, content_type=MIMETYPE_APPLICATION_JSON
        )  # 422

    await db.update_user(
        dict(user),
        {"password_hash": encrypt_password(passwords.new.get_secret_value())},
    )

    return flash_response(MSG_PASSWORD_CHANGED)
