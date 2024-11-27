# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any

from fastapi import APIRouter, status
from models_library.api_schemas_webserver.auth import (
    AccountRequestInfo,
    ApiKeyCreate,
    ApiKeyGet,
    UnregisterCheck,
)
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError, Log
from pydantic import BaseModel, Field, confloat
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.login._2fa_handlers import Resend2faBody
from simcore_service_webserver.login._auth_handlers import (
    LoginBody,
    LoginNextPage,
    LoginTwoFactorAuthBody,
    LogoutBody,
)
from simcore_service_webserver.login.handlers_change import (
    ChangeEmailBody,
    ChangePasswordBody,
    ResetPasswordBody,
)
from simcore_service_webserver.login.handlers_confirmation import (
    PhoneConfirmationBody,
    ResetPasswordConfirmation,
)
from simcore_service_webserver.login.handlers_registration import (
    InvitationCheck,
    InvitationInfo,
    RegisterBody,
    RegisterPhoneBody,
    RegisterPhoneNextPage,
)

router = APIRouter(prefix=f"/{API_VTAG}", tags=["auth"])


@router.post(
    "/auth/request-account",
    operation_id="request_product_account",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def request_product_account(_body: AccountRequestInfo):
    ...


@router.post(
    "/auth/register/invitations:check",
    response_model=Envelope[InvitationInfo],
    operation_id="auth_check_registration_invitation",
)
async def check_registration_invitation(check: InvitationCheck):
    """Check invitation and returns associated email or None"""


@router.post(
    "/auth/register",
    response_model=Envelope[Log],
    operation_id="auth_register",
)
async def register(_body: RegisterBody):
    """User registration"""


@router.post(
    "/auth/unregister",
    response_model=Envelope[Log],
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_409_CONFLICT: {"model": EnvelopedError}},
)
async def unregister_account(_body: UnregisterCheck):
    ...


@router.post(
    "/auth/verify-phone-number",
    response_model=Envelope[RegisterPhoneNextPage],
    operation_id="auth_register_phone",
)
async def register_phone(_body: RegisterPhoneBody):
    """user tries to verify phone number for 2 Factor Authentication when registering"""


@router.post(
    "/auth/validate-code-register",
    response_model=Envelope[Log],
    operation_id="auth_phone_confirmation",
)
async def phone_confirmation(_body: PhoneConfirmationBody):
    """user enters 2 Factor Authentication code when registering"""


@router.post(
    "/auth/login",
    response_model=Envelope[LoginNextPage],
    status_code=status.HTTP_201_CREATED,
    operation_id="auth_login",
    responses={
        # status.HTTP_503_SERVICE_UNAVAILABLE
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "unauthorized reset due to invalid token code",
        }
    },
)
async def login(_body: LoginBody):
    """user logs in"""


@router.post(
    "/auth/validate-code-login",
    response_model=Envelope[Log],
    operation_id="auth_login_2fa",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "unauthorized reset due to invalid token code",
        }
    },
)
async def login_2fa(_body: LoginTwoFactorAuthBody):
    """user enters 2 Factor Authentication code when login in"""


@router.post(
    "/auth/two_factor:resend",
    response_model=Envelope[Log],
    operation_id="auth_resend_2fa_code",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "unauthorized reset due to invalid token code",
        }
    },
)
async def resend_2fa_code(resend: Resend2faBody):
    """Resends 2FA either via email or sms"""


@router.post(
    "/auth/logout",
    response_model=Envelope[Log],
    operation_id="auth_logout",
)
async def logout(_body: LogoutBody):
    """user logout"""


@router.get(
    "/auth:check",
    operation_id="check_authentication",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "unauthorized reset due to invalid token code",
        }
    },
)
async def check_auth():
    """checks if user is authenticated in the platform"""


@router.post(
    "/auth/reset-password",
    response_model=Envelope[Log],
    operation_id="auth_reset_password",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": EnvelopedError}},
)
async def reset_password(_body: ResetPasswordBody):
    """a non logged-in user requests a password reset"""


@router.post(
    "/auth/reset-password/{code}",
    response_model=Envelope[Log],
    operation_id="auth_reset_password_allowed",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "unauthorized reset due to invalid token code",
        }
    },
)
async def reset_password_allowed(code: str, _body: ResetPasswordConfirmation):
    """changes password using a token code without being logged in"""


@router.post(
    "/auth/change-email",
    response_model=Envelope[Log],
    operation_id="auth_change_email",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "unauthorized user. Login required",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": EnvelopedError,
            "description": "unable to send confirmation email",
        },
    },
    # Disabled in https://github.com/ITISFoundation/osparc-simcore/pull/5472
    include_in_schema=False,
)
async def change_email(_body: ChangeEmailBody):
    """logged in user changes email"""


class PasswordCheckSchema(BaseModel):
    strength: confloat(ge=0.0, le=1.0) = Field(  # type: ignore
        ...,
        description="The strength of the password ranges from 0 (extremely weak) and 1 (extremely strong)",
    )
    rating: str | None = Field(
        None, description="Human readable rating from infinitely weak to very strong"
    )
    improvements: Any | None = None


@router.post(
    "/auth/change-password",
    response_model=Envelope[Log],
    operation_id="auth_change_password",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "unauthorized user. Login required",
        },
        status.HTTP_409_CONFLICT: {
            "model": EnvelopedError,
            "description": "mismatch between new and confirmation passwords",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": EnvelopedError,
            "description": "current password is invalid",
        },
    },
)
async def change_password(_body: ChangePasswordBody):
    """logged in user changes password"""


@router.get(
    "/auth/confirmation/{code}",
    response_model=Envelope[Log],
    operation_id="auth_confirmation",
    responses={
        "3XX": {
            "description": "redirection to specific ui application page",
        },
    },
)
async def email_confirmation(code: str):
    """email link sent to user to confirm an action"""


@router.get(
    "/auth/api-keys",
    operation_id="list_api_keys",
    responses={
        status.HTTP_200_OK: {
            "description": "returns the display names of API keys",
            "model": list[str],
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "key name requested is invalid",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "requires login to  list keys",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "not enough permissions to list keys",
        },
    },
)
async def list_api_keys():
    """lists display names of API keys by this user"""


@router.post(
    "/auth/api-keys",
    operation_id="create_api_key",
    responses={
        status.HTTP_200_OK: {
            "description": "Authorization granted returning API key",
            "model": ApiKeyGet,
        },
        status.HTTP_400_BAD_REQUEST: {
            "description": "key name requested is invalid",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "requires login to  list keys",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "not enough permissions to list keys",
        },
    },
)
async def create_api_key(_body: ApiKeyCreate):
    """creates API keys to access public API"""


@router.delete(
    "/auth/api-keys",
    operation_id="delete_api_key",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_204_NO_CONTENT: {
            "description": "api key successfully deleted",
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "requires login to  delete a key",
        },
        status.HTTP_403_FORBIDDEN: {
            "description": "not enough permissions to delete a key",
        },
    },
)
async def delete_api_key(_body: ApiKeyCreate):
    """deletes API key by name"""


@router.get(
    "/auth/captcha",
    operation_id="request_captcha",
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_200_OK: {"content": {"image/png": {}}}},
)
async def request_captcha():
    ...
