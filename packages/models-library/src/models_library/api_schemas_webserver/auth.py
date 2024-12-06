from datetime import timedelta
from typing import Annotated, Any

from models_library.basic_types import IDStr
from pydantic import AliasGenerator, ConfigDict, Field, HttpUrl, SecretStr
from pydantic.alias_generators import to_camel

from ..emails import LowerCaseEmailStr
from ._base import InputSchema, OutputSchema


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


class ApiKeyCreateRequest(OutputSchema):
    display_name: Annotated[str, Field(..., min_length=3)]
    expiration: timedelta | None = Field(
        None,
        description="Time delta from creation time to expiration. If None, then it does not expire.",
    )

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            validation_alias=to_camel,
        ),
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "displayName": "test-api-forever",
                },
                {
                    "displayName": "test-api-for-one-day",
                    "expiration": 60 * 60 * 24,
                },
                {
                    "displayName": "test-api-for-another-day",
                    "expiration": "24:00:00",
                },
            ]
        },
    )


class ApiKeyCreateResponse(ApiKeyCreateRequest):
    id: IDStr
    api_base_url: HttpUrl
    api_key: str
    api_secret: str

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "42",
                    "display_name": "test-api-forever",
                    "api_base_url": "http://api.osparc.io/v0",  # NOSONAR
                    "api_key": "key",
                    "api_secret": "secret",
                },
                {
                    "id": "48",
                    "display_name": "test-api-for-one-day",
                    "expiration": 60 * 60 * 24,
                    "api_base_url": "http://api.sim4life.io/v0",  # NOSONAR
                    "api_key": "key",
                    "api_secret": "secret",
                },
                {
                    "id": "54",
                    "display_name": "test-api-for-another-day",
                    "expiration": "24:00:00",
                    "api_base_url": "http://api.osparc-master.io/v0",  # NOSONAR
                    "api_key": "key",
                    "api_secret": "secret",
                },
            ]
        },
    )


class ApiKeyGet(OutputSchema):
    id: IDStr
    display_name: Annotated[str, Field(..., min_length=3)]

    model_config = ConfigDict(
        alias_generator=AliasGenerator(
            serialization_alias=to_camel,
        ),
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "42",
                    "display_name": "myapi",
                },
            ]
        },
    )
