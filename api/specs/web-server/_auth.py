# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any

from fastapi import APIRouter, status
from models_library.api_schemas_webserver.auth import (
    AccountRequestInfo,
    UnregisterCheck,
)
from models_library.generics import Envelope
from models_library.rest_error import EnvelopedError, Log
from pydantic import BaseModel, Field, confloat
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.login._controller.rest.auth import (
    LoginBody,
    LoginNextPage,
    LoginTwoFactorAuthBody,
    LogoutBody,
)
from simcore_service_webserver.login._controller.rest.change import (
    ChangeEmailBody,
    ChangePasswordBody,
    ResetPasswordBody,
)
from simcore_service_webserver.login._controller.rest.confirmation import (
    PhoneConfirmationBody,
    ResetPasswordConfirmation,
)
from simcore_service_webserver.login._controller.rest.registration import (
    InvitationCheck,
    InvitationInfo,
    RegisterBody,
    RegisterPhoneBody,
    RegisterPhoneNextPage,
)
from simcore_service_webserver.login._controller.rest.twofa import Resend2faBody

router = APIRouter(prefix=f"/{API_VTAG}", tags=["auth"])


@router.post(
    "/auth/request-account",
    operation_id="request_product_account",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def request_product_account(_body: AccountRequestInfo): ...


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
async def unregister_account(_body: UnregisterCheck): ...


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
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
        }
    },
)
async def check_auth():
    """checks whether user request is authenticated"""


@router.post(
    "/auth/reset-password",
    response_model=Envelope[Log],
    operation_id="initiate_reset_password",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": EnvelopedError}},
)
async def initiate_reset_password(_body: ResetPasswordBody): ...


@router.post(
    "/auth/reset-password/{code}",
    response_model=Envelope[Log],
    operation_id="complete_reset_password",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": EnvelopedError,
            "description": "Invalid token code",
        }
    },
)
async def complete_reset_password(code: str, _body: ResetPasswordConfirmation): ...


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
    "/auth/captcha",
    operation_id="create_captcha",
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_200_OK: {"content": {"image/png": {}}}},
)
async def create_captcha(): ...
