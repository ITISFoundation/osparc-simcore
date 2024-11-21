from datetime import timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..emails import LowerCaseEmailStr
from ._base import InputSchema


class AccountRequestInfo(InputSchema):
    form: dict[str, Any]
    captcha: str

    model_config = ConfigDict(
        str_strip_whitespace=True,
        str_max_length=200,
        # NOTE: this is just informative. The format of the form is defined
        # currently in the front-end and it might change
        # SEE image in  https://github.com/ITISFoundation/osparc-simcore/pull/5378
        json_schema_extra={
            "example": {
                "form": {
                    "firstName": "James",
                    "lastName": "Maxwel",
                    "email": "maxwel@email.com",
                    "phone": "+1 123456789",
                    "company": "EM Com",
                    "address": "Infinite Loop",
                    "city": "Washington",
                    "postalCode": "98001",
                    "country": "USA",
                    "application": "Antenna_Design",
                    "description": "Description of something",
                    "hear": "Search_Engine",
                    "privacyPolicy": True,
                    "eula": True,
                },
                "captcha": "A12B34",
            }
        },
    )


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

    model_config = ConfigDict(
        json_schema_extra={
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
    )


class ApiKeyGet(BaseModel):
    display_name: str = Field(..., min_length=3)
    api_key: str
    api_secret: str

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {"display_name": "myapi", "api_key": "key", "api_secret": "secret"},
            ]
        },
    )
