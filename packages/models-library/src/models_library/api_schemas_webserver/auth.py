from datetime import timedelta
from typing import Any, ClassVar

from pydantic import BaseModel, Field, SecretStr

from ..emails import LowerCaseEmailStr
from ._base import InputSchema


class AccountRequestInfo(InputSchema):
    form: dict[str, Any]


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

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "display_name": "test-api-forever",
                },
                {
                    "display_name": "test-api-for-one-day",
                    "expiration": 60 * 60 * 24,
                },
                {
                    "display_name": "test-api-for-another-day",
                    "expiration": "24:00:00",
                },
            ]
        }


class ApiKeyGet(BaseModel):
    display_name: str = Field(..., min_length=3)
    api_key: str
    api_secret: str

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {"display_name": "myapi", "api_key": "key", "api_secret": "secret"},
            ]
        }
