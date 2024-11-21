import logging
from contextlib import suppress
from json import JSONDecodeError

from aiohttp import web
from aiohttp.web import RouteTableDef
from common_library.error_codes import create_error_code
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    SecretStr,
    TypeAdapter,
    ValidationError,
    field_validator,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.logging_errors import create_troubleshotting_log_kwargs
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.errors import UniqueViolation
from yarl import URL

from ..products.api import Product, get_current_product
from ..security.api import encrypt_password
from ..session.access_policies import session_access_required
from ..utils import MINUTE
from ..utils_aiohttp import create_redirect_to_page_response
from ..utils_rate_limiting import global_rate_limit_route
from ._2fa_api import delete_2fa_code, get_2fa_code
from ._confirmation import validate_confirmation_code
from ._constants import (
    MSG_PASSWORD_CHANGE_NOT_ALLOWED,
    MSG_PASSWORD_CHANGED,
    MSG_UNAUTHORIZED_PHONE_CONFIRMATION,
)
from ._models import InputSchema, check_confirm_password_match
from ._registration import InvitationData
from ._security import login_granted_response
from .settings import (
    LoginOptions,
    LoginSettingsForProduct,
    get_plugin_options,
    get_plugin_settings,
)
from .storage import AsyncpgStorage, ConfirmationTokenDict, get_plugin_storage
from .utils import (
    ACTIVE,
    CHANGE_EMAIL,
    REGISTRATION,
    RESET_PASSWORD,
    flash_response,
    notify_user_confirmation,
)

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


class _PathParam(BaseModel):
    code: SecretStr


def _parse_extra_credits_in_usd_or_none(
    confirmation: ConfirmationTokenDict,
) -> PositiveInt | None:
    with suppress(ValidationError, JSONDecodeError):
        confirmation_data = confirmation.get("data", "EMPTY") or "EMPTY"
        invitation = InvitationData.model_validate_json(confirmation_data)
        return invitation.extra_credits_in_usd
    return None


async def _handle_confirm_registration(
    app: web.Application,
    product_name: ProductName,
    confirmation: ConfirmationTokenDict,
):
    db: AsyncpgStorage = get_plugin_storage(app)
    user_id = confirmation["user_id"]

    # activate user and consume confirmation token
    await db.delete_confirmation_and_update_user(
        user_id=user_id,
        updates={"status": ACTIVE},
        confirmation=confirmation,
    )

    await notify_user_confirmation(
        app,
        user_id=user_id,
        product_name=product_name,
        extra_credits_in_usd=_parse_extra_credits_in_usd_or_none(confirmation),
    )


async def _handle_confirm_change_email(
    app: web.Application, confirmation: ConfirmationTokenDict
):
    db: AsyncpgStorage = get_plugin_storage(app)
    user_id = confirmation["user_id"]

    # update and consume confirmation token
    await db.delete_confirmation_and_update_user(
        user_id=user_id,
        updates={
            "email": TypeAdapter(LowerCaseEmailStr).validate_python(
                confirmation["data"]
            )
        },
        confirmation=confirmation,
    )


@routes.get("/v0/auth/confirmation/{code}", name="auth_confirmation")
async def validate_confirmation_and_redirect(request: web.Request):
    """Handles email confirmation by checking a code passed as query parameter

    Retrieves confirmation key and redirects back to some location front-end

    * registration, change-email:
        - sets user as active
        - redirects to login
    * reset-password:
        - redirects to login
        - attaches page and token info onto the url
        - info appended as fragment, e.g. https://osparc.io#reset-password?code=131234
        - front-end should interpret that info as:
            - show the reset-password page
            - use the token to submit a POST /v0/auth/confirmation/{code} and finalize reset action
    """
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    path_params = parse_request_path_parameters_as(_PathParam, request)

    confirmation: ConfirmationTokenDict | None = await validate_confirmation_code(
        path_params.code.get_secret_value(),
        db=db,
        cfg=cfg,
    )

    redirect_to_login_url = URL(cfg.LOGIN_REDIRECT)
    if confirmation and (action := confirmation["action"]):
        try:
            if action == REGISTRATION:
                await _handle_confirm_registration(
                    app=request.app,
                    product_name=product.name,
                    confirmation=confirmation,
                )
                redirect_to_login_url = redirect_to_login_url.with_fragment(
                    "?registered=true"
                )

            elif action == CHANGE_EMAIL:
                await _handle_confirm_change_email(
                    app=request.app, confirmation=confirmation
                )

            elif action == RESET_PASSWORD:
                #
                # NOTE: By using fragments (instead of queries or path parameters),
                # the browser does NOT reloads page
                #
                redirect_to_login_url = redirect_to_login_url.with_fragment(
                    f"reset-password?code={path_params.code.get_secret_value()}"
                )

            _logger.info(
                "Confirms %s %s -> %s",
                action.upper(),
                f"{confirmation=}",
                f"{redirect_to_login_url=}",
            )

        except Exception as err:  # pylint: disable=broad-except
            error_code = create_error_code(err)
            user_error_msg = (
                f"Sorry, we cannot confirm your {action}."
                "Please try again in a few moments. "
                f"If the problem persist please contact support attaching this code ({error_code})"
            )

            _logger.exception(
                **create_troubleshotting_log_kwargs(
                    user_error_msg,
                    error=err,
                    error_code=error_code,
                    tip="Failed during email_confirmation",
                )
            )

            raise create_redirect_to_page_response(
                request.app,
                page="error",
                message=user_error_msg,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from err

    raise web.HTTPFound(location=redirect_to_login_url)


class PhoneConfirmationBody(InputSchema):
    email: LowerCaseEmailStr
    phone: str = Field(
        ..., description="Phone number E.164, needed on the deployments with 2FA"
    )
    code: SecretStr


@routes.post("/v0/auth/validate-code-register", name="auth_phone_confirmation")
@global_rate_limit_route(number_of_requests=5, interval_seconds=MINUTE)
@session_access_required(
    name="auth_phone_confirmation",
    unauthorized_reason=MSG_UNAUTHORIZED_PHONE_CONFIRMATION,
)
async def phone_confirmation(request: web.Request):
    product: Product = get_current_product(request)
    settings: LoginSettingsForProduct = get_plugin_settings(
        request.app, product_name=product.name
    )

    db: AsyncpgStorage = get_plugin_storage(request.app)

    if not settings.LOGIN_2FA_REQUIRED:
        raise web.HTTPServiceUnavailable(
            reason="Phone registration is not available",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    request_body = await parse_request_body_as(PhoneConfirmationBody, request)

    if (
        expected := await get_2fa_code(request.app, request_body.email)
    ) and request_body.code.get_secret_value() == expected:
        # consumes code
        await delete_2fa_code(request.app, request_body.email)

        # updates confirmed phone number
        try:
            user = await db.get_user({"email": request_body.email})
            assert user is not None  # nosec
            await db.update_user(dict(user), {"phone": request_body.phone})

        except UniqueViolation as err:
            raise web.HTTPUnauthorized(
                reason="Invalid phone number",
                content_type=MIMETYPE_APPLICATION_JSON,
            ) from err

        return await login_granted_response(request, user=dict(user))

    # fails because of invalid or no code
    raise web.HTTPUnauthorized(
        reason="Invalid 2FA code", content_type=MIMETYPE_APPLICATION_JSON
    )


class ResetPasswordConfirmation(InputSchema):
    password: SecretStr
    confirm: SecretStr

    _password_confirm_match = field_validator("confirm")(check_confirm_password_match)


@routes.post("/v0/auth/reset-password/{code}", name="auth_reset_password_allowed")
async def reset_password(request: web.Request):
    """Changes password using a token code without being logged in

    Code is provided via email by calling first submit_request_to_reset_password
    """
    db: AsyncpgStorage = get_plugin_storage(request.app)
    cfg: LoginOptions = get_plugin_options(request.app)
    product: Product = get_current_product(request)

    path_params = parse_request_path_parameters_as(_PathParam, request)
    request_body = await parse_request_body_as(ResetPasswordConfirmation, request)

    confirmation = await validate_confirmation_code(
        code=path_params.code.get_secret_value(), db=db, cfg=cfg
    )

    if confirmation:
        user = await db.get_user({"id": confirmation["user_id"]})
        assert user  # nosec

        await db.update_user(
            dict(user),
            {
                "password_hash": encrypt_password(
                    request_body.password.get_secret_value()
                )
            },
        )
        await db.delete_confirmation(confirmation)

        return flash_response(MSG_PASSWORD_CHANGED)

    raise web.HTTPUnauthorized(
        reason=MSG_PASSWORD_CHANGE_NOT_ALLOWED.format(
            support_email=product.support_email
        ),
        content_type=MIMETYPE_APPLICATION_JSON,
    )  # 401
