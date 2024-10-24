import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.authentification import TwoFactorAuthentificationMethod
from models_library.emails import LowerCaseEmailStr
from pydantic import BaseModel, Field, PositiveInt, SecretStr, TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.models.users import UserRole

from .._meta import API_VTAG
from ..products.api import Product, get_current_product
from ..security.api import forget_identity
from ..session.access_policies import (
    on_success_grant_session_access_to,
    session_access_required,
)
from ..users import preferences_api as user_preferences_api
from ..utils_aiohttp import NextPage
from ._2fa_api import (
    create_2fa_code,
    delete_2fa_code,
    get_2fa_code,
    mask_phone_number,
    send_email_code,
    send_sms_code,
)
from ._auth_api import (
    check_authorized_user_credentials_or_raise,
    check_authorized_user_in_product_or_raise,
    get_user_by_email,
)
from ._constants import (
    CODE_2FA_EMAIL_CODE_REQUIRED,
    CODE_2FA_SMS_CODE_REQUIRED,
    CODE_PHONE_NUMBER_REQUIRED,
    MAX_2FA_CODE_RESEND,
    MAX_2FA_CODE_TRIALS,
    MSG_2FA_CODE_SENT,
    MSG_EMAIL_SENT,
    MSG_LOGGED_OUT,
    MSG_PHONE_MISSING,
    MSG_UNAUTHORIZED_LOGIN_2FA,
    MSG_WRONG_2FA_CODE__EXPIRED,
    MSG_WRONG_2FA_CODE__INVALID,
)
from ._models import InputSchema
from ._security import login_granted_response
from .decorators import login_required
from .errors import handle_login_exceptions
from .settings import LoginSettingsForProduct, get_plugin_settings
from .storage import AsyncpgStorage, get_plugin_storage
from .utils import envelope_response, flash_response, notify_user_logout

log = logging.getLogger(__name__)


routes = RouteTableDef()


class LoginBody(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr


class CodePageParams(BaseModel):
    message: str
    expiration_2fa: PositiveInt | None = None
    next_url: str | None = None


class LoginNextPage(NextPage[CodePageParams]):
    ...


@routes.post(f"/{API_VTAG}/auth/login", name="auth_login")
@on_success_grant_session_access_to(
    name="auth_register_phone",
    max_access_count=MAX_2FA_CODE_TRIALS,
)
@on_success_grant_session_access_to(
    name="auth_login_2fa",
    max_access_count=MAX_2FA_CODE_TRIALS,
)
@on_success_grant_session_access_to(
    name="auth_resend_2fa_code",
    max_access_count=MAX_2FA_CODE_RESEND,
)
@handle_login_exceptions
async def login(request: web.Request):
    """Login: user submits an email (identification) and a password

    If 2FA is enabled, then the login continues with a second request to login_2fa
    """
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )
    login_data = await parse_request_body_as(LoginBody, request)

    # Authenticate user and verify access to the product
    user = await check_authorized_user_credentials_or_raise(
        user=await get_user_by_email(request.app, email=login_data.email),
        password=login_data.password.get_secret_value(),
        product=product,
    )
    await check_authorized_user_in_product_or_raise(
        request.app, user=user, product=product
    )

    # Check if user role allows skipping 2FA or if 2FA is not required
    skip_2fa = UserRole(user["role"]) == UserRole.TESTER
    if skip_2fa or not settings.LOGIN_2FA_REQUIRED:
        return await login_granted_response(request, user=user)

    # 2FA login process continuation
    user_2fa_preference = await user_preferences_api.get_frontend_user_preference(
        request.app,
        user_id=user["id"],
        product_name=product.name,
        preference_class=user_preferences_api.TwoFAFrontendUserPreference,
    )
    if not user_2fa_preference:
        user_2fa_authentification_method = TwoFactorAuthentificationMethod.SMS
        preference_id = (
            user_preferences_api.TwoFAFrontendUserPreference().preference_identifier
        )
        await user_preferences_api.set_frontend_user_preference(
            request.app,
            user_id=user["id"],
            product_name=product.name,
            frontend_preference_identifier=preference_id,
            value=user_2fa_authentification_method,
        )
    else:
        user_2fa_authentification_method = TypeAdapter(
            TwoFactorAuthentificationMethod
        ).validate_python(user_2fa_preference.value)

    if user_2fa_authentification_method == TwoFactorAuthentificationMethod.DISABLED:
        return await login_granted_response(request, user=user)

    # Check phone for SMS authentication
    if (
        user_2fa_authentification_method == TwoFactorAuthentificationMethod.SMS
        and not user["phone"]
    ):
        return envelope_response(
            # LoginNextPage
            {
                "name": CODE_PHONE_NUMBER_REQUIRED,
                "parameters": {
                    "message": MSG_PHONE_MISSING,
                    "next_url": f"{request.app.router['auth_register_phone'].url_for()}",
                },
            },
            status=status.HTTP_202_ACCEPTED,
        )

    code = await create_2fa_code(
        app=request.app,
        user_email=user["email"],
        expiration_in_seconds=settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
    )

    if user_2fa_authentification_method == TwoFactorAuthentificationMethod.SMS:
        # create sms 2FA
        assert user["phone"]  # nosec
        assert settings.LOGIN_2FA_REQUIRED  # nosec
        assert settings.LOGIN_TWILIO  # nosec
        assert product.twilio_messaging_sid  # nosec

        await send_sms_code(
            phone_number=user["phone"],
            code=code,
            twilio_auth=settings.LOGIN_TWILIO,
            twilio_messaging_sid=product.twilio_messaging_sid,
            twilio_alpha_numeric_sender=product.twilio_alpha_numeric_sender_id,
            first_name=user["first_name"],
            user_id=user["id"],
        )

        return envelope_response(
            # LoginNextPage
            {
                "name": CODE_2FA_SMS_CODE_REQUIRED,
                "parameters": {
                    "message": MSG_2FA_CODE_SENT.format(
                        phone_number=mask_phone_number(user["phone"])
                    ),
                    "expiration_2fa": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
                },
            },
            status=status.HTTP_202_ACCEPTED,
        )

    # otherwise create email f2a
    assert (
        user_2fa_authentification_method == TwoFactorAuthentificationMethod.EMAIL
    )  # nosec
    await send_email_code(
        request,
        user_email=user["email"],
        support_email=product.support_email,
        code=code,
        first_name=user["first_name"] or user["name"],
        product=product,
        user_id=user["id"],
    )
    return envelope_response(
        {
            "name": CODE_2FA_EMAIL_CODE_REQUIRED,
            "parameters": {
                "message": MSG_EMAIL_SENT.format(email=user["email"]),
                "expiration_2fa": settings.LOGIN_2FA_CODE_EXPIRATION_SEC,
            },
        },
        status=status.HTTP_202_ACCEPTED,
    )


class LoginTwoFactorAuthBody(InputSchema):
    email: LowerCaseEmailStr
    code: SecretStr


@routes.post(f"/{API_VTAG}/auth/validate-code-login", name="auth_login_2fa")
@session_access_required(
    "auth_login_2fa",
    unauthorized_reason=MSG_UNAUTHORIZED_LOGIN_2FA,
)
async def login_2fa(request: web.Request):
    """Login (continuation): Submits 2FA code"""
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )
    db: AsyncpgStorage = get_plugin_storage(request.app)

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="2FA login is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    # validates input params
    login_2fa_ = await parse_request_body_as(LoginTwoFactorAuthBody, request)

    # validates code
    _expected_2fa_code = await get_2fa_code(request.app, login_2fa_.email)
    if not _expected_2fa_code:
        raise web.HTTPUnauthorized(
            reason=MSG_WRONG_2FA_CODE__EXPIRED, content_type=MIMETYPE_APPLICATION_JSON
        )
    if login_2fa_.code.get_secret_value() != _expected_2fa_code:
        raise web.HTTPUnauthorized(
            reason=MSG_WRONG_2FA_CODE__INVALID, content_type=MIMETYPE_APPLICATION_JSON
        )

    user = await db.get_user({"email": login_2fa_.email})
    assert user is not None  # nosec

    # NOTE: a priviledge user should not have called this entrypoint
    assert UserRole(user["role"]) <= UserRole.USER  # nosec

    # dispose since code was used
    await delete_2fa_code(request.app, login_2fa_.email)

    return await login_granted_response(request, user=dict(user))


class LogoutBody(InputSchema):
    client_session_id: str | None = Field(
        None, examples=["5ac57685-c40f-448f-8711-70be1936fd63"]
    )


@routes.post(f"/{API_VTAG}/auth/logout", name="auth_logout")
@login_required
async def logout(request: web.Request) -> web.Response:
    user_id = request.get(RQT_USERID_KEY, -1)

    logout_ = await parse_request_body_as(LogoutBody, request)

    # Keep log message: https://github.com/ITISFoundation/osparc-simcore/issues/3200
    with log_context(
        log,
        logging.INFO,
        "logout of %s for %s",
        f"{user_id=}",
        f"{logout_.client_session_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        response = flash_response(MSG_LOGGED_OUT, "INFO")
        await notify_user_logout(request.app, user_id, logout_.client_session_id)
        await forget_identity(request, response)

        return response


@routes.get(f"/{API_VTAG}/auth:check", name="check_authentication")
@login_required
async def check_auth(request: web.Request) -> web.Response:
    # lightweight endpoint for checking if users are authenticated
    # used primarily by Traefik auth middleware to verify session cookies

    # NOTE: for future development
    # if database access is added here, services like jupyter-math
    # which load a lot of resources will have a big performance hit
    # consider caching some properties required by this endpoint or rely on Redis

    assert request  # nosec

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
