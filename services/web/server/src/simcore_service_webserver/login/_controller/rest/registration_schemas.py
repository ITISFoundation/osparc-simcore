import logging
from typing import Annotated, Literal

from models_library.api_schemas_webserver.users import PhoneNumberStr
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
    invitation: Annotated[str, Field(description="Invitation code")]


class InvitationInfo(InputSchema):
    email: Annotated[
        LowerCaseEmailStr | None,
        Field(description="Email associated to invitation or None"),
    ] = None


class RegisterBody(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr
    confirm: Annotated[SecretStr | None, Field(description="Password confirmation")] = (
        None
    )
    invitation: Annotated[str | None, Field(description="Invitation code")] = None

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
    phone: Annotated[
        PhoneNumberStr,
        Field(description="Phone number E.164, needed on the deployments with 2FA"),
    ]


class _PageParams(BaseModel):
    expiration_2fa: PositiveInt | None = None


class RegisterPhoneNextPage(NextPage[_PageParams]):
    logger: Annotated[str, Field(deprecated=True)] = "user"
    level: Literal["INFO", "WARNING", "ERROR"] = "INFO"
    message: str
