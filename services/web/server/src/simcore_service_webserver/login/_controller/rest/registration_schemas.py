import logging
from typing import Literal

from models_library.emails import LowerCaseEmailStr
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    SecretStr,
    field_validator,
)

from ....utils_aiohttp import NextPage
from ..._models import InputSchema, check_confirm_password_match

_logger = logging.getLogger(__name__)


class InvitationCheck(InputSchema):
    invitation: str = Field(..., description="Invitation code")


class InvitationInfo(InputSchema):
    email: LowerCaseEmailStr | None = Field(
        None, description="Email associated to invitation or None"
    )


class RegisterBody(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr
    confirm: SecretStr | None = Field(None, description="Password confirmation")
    invitation: str | None = Field(None, description="Invitation code")

    _password_confirm_match = field_validator("confirm")(check_confirm_password_match)
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "foo@mymail.com",
                    "password": "my secret",  # NOSONAR
                    "confirm": "my secret",  # optional
                    "invitation": "33c451d4-17b7-4e65-9880-694559b8ffc2",  # optional only active
                }
            ]
        }
    )


class RegisterPhoneBody(InputSchema):
    email: LowerCaseEmailStr
    phone: str = Field(
        ..., description="Phone number E.164, needed on the deployments with 2FA"
    )


class _PageParams(BaseModel):
    expiration_2fa: PositiveInt | None = None


class RegisterPhoneNextPage(NextPage[_PageParams]):
    logger: str = Field("user", deprecated=True)
    level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    message: str
