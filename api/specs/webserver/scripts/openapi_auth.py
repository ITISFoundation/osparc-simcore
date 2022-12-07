""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Any, Optional, Union

from _common import Error, Log
from fastapi import FastAPI, status
from models_library.generics import Envelope
from pydantic import BaseModel, EmailStr, Field, confloat
from simcore_service_webserver.login.api_keys_handlers import ApiKeyCreate, ApiKeyGet
from simcore_service_webserver.login.handlers_registration import RegistrationCreate

app = FastAPI(redoc_url=None)

TAGS: list[Union[str, Enum]] = [
    "authentication",
]


@app.post(
    "/auth/register",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_register",
)
async def register(registration: RegistrationCreate):
    """User registration"""


class Verify2FAPhone(BaseModel):
    email: EmailStr
    phone: str = Field(
        ..., description="Phone number E.164, needed on the deployments with 2FA"
    )


@app.post(
    "/auth/verify-phone-number",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_verify_2fa_phone",
)
async def register_phone(registration: Verify2FAPhone):
    """user tries to verify phone number for 2 Factor Authentication when registering"""


class Validate2FAPhone(BaseModel):
    email: str
    phone: str = Field(
        ..., description="Phone number E.164, needed on the deployments with 2FA"
    )
    code: str


@app.post(
    "/auth/validate-code-register",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_validate_2fa_register",
)
async def phone_confirmation(confirmation: Validate2FAPhone):
    """user enters 2 Factor Authentication code when registering"""


class LoginForm(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None


class Login2FAForm(BaseModel):
    email: str
    code: str


class LogoutRequest(BaseModel):
    client_session_id: Optional[str] = Field(
        None, example="5ac57685-c40f-448f-8711-70be1936fd63"
    )


@app.post(
    "/auth/login",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_login",
)
async def login(authentication: LoginForm):
    """user logs in"""


@app.post(
    "/auth/validate-code-login",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_login_2fa",
)
async def login_2fa(authentication: Login2FAForm):
    """user enters 2 Factor Authentication code when login in"""


@app.post(
    "/auth/logout",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_logout",
)
async def logout(data: LogoutRequest):
    """user logout"""


class ResetPasswordRequest(BaseModel):
    email: str


@app.post(
    "/auth/reset-password",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_reset_password",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Envelope[Error]}},
)
async def reset_password(data: ResetPasswordRequest):
    """a non logged-in user requests a password reset"""


class ResetPasswordForm(BaseModel):
    password: str
    confirm: str


@app.post(
    "/auth/reset-password/{code}",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_reset_password_allowed",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": Envelope[Error],
            "description": "unauthorized reset due to invalid token code",
        }
    },
)
async def reset_password_allowed(code: str, data: ResetPasswordForm):
    """changes password using a token code without being logged in"""


class ChangeEmailForm(BaseModel):
    email: str


@app.post(
    "/auth/change-email",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_change_email",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": Envelope[Error],
            "description": "unauthorized user. Login required",
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": Envelope[Error],
            "description": "unable to send confirmation email",
        },
    },
)
async def change_email(data: ChangeEmailForm):
    """logged in user changes email"""


class ChangePasswordForm(BaseModel):
    current: str
    new: str
    confirm: str


class PasswordCheckSchema(BaseModel):
    strength: confloat(ge=0.0, le=1.0) = Field(  # type: ignore
        ...,
        description="The strength of the password ranges from 0 (extremely weak) and 1 (extremely strong)",
    )
    rating: Optional[str] = Field(
        None, description="Human readable rating from infinitely weak to very strong"
    )
    improvements: Optional[Any] = None


@app.post(
    "/auth/change-password",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_change_password",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": Envelope[Error],
            "description": "unauthorized user. Login required",
        },
        status.HTTP_409_CONFLICT: {
            "model": Envelope[Error],
            "description": "mismatch between new and confirmation passwords",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": Envelope[Error],
            "description": "current password is invalid",
        },
    },
)
async def change_password(data: ChangePasswordForm):
    """logged in user changes password"""


@app.get(
    "/auth/confirmation/{code}",
    response_model=Envelope[Log],
    tags=TAGS,
    operation_id="auth_confirmation",
    responses={
        "3XX": {
            "description": "redirection to specific ui application page",
        },
    },
)
async def email_confirmation(code: str):
    """email link sent to user to confirm an action"""


@app.get(
    "/auth/api-keys",
    tags=TAGS,
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
async def list_api_keys(code: str):
    """lists display names of API keys by this user"""


@app.post(
    "/auth/api-keys",
    tags=TAGS,
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
async def create_api_key(data: ApiKeyCreate):
    """creates API keys to access public API"""


@app.delete(
    "/auth/api-keys",
    tags=TAGS,
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
async def delete_api_key(data: ApiKeyCreate):
    """deletes API key by name"""


if __name__ == "__main__":

    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-auth.ignore.yaml")
