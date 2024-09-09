from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..emails import LowerCaseEmailStr
from ._base import InputSchema


class AccountRequestInfo(InputSchema):
    form: dict[str, Any]
    captcha: str
    model_config = ConfigDict(str_strip_whitespace=True, str_max_length=200)


class UnregisterCheck(InputSchema):
    email: LowerCaseEmailStr
    password: SecretStr


#
# API keys
#


class ApiKeyCreate(BaseModel):
    display_name: str = Field(..., min_length=3)
    expiration: timedelta | None = Field(
        None,
        description="Time delta from creation time to expiration. If None, then it does not expire.",
    )
    model_config = ConfigDict()


class ApiKeyGet(BaseModel):
    display_name: str = Field(..., min_length=3)
    api_key: str
    api_secret: str
    model_config = ConfigDict()
