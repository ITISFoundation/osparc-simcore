from typing import Annotated

from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .utils_validators import validate_nullable_url


class SSMSettings(BaseCustomSettings):
    SSM_ACCESS_KEY_ID: SecretStr
    SSM_ENDPOINT: Annotated[
        str | None,
        BeforeValidator(validate_nullable_url),
        Field(description="do not define if using standard AWS"),
    ] = None
    SSM_REGION_NAME: str = "us-east-1"
    SSM_SECRET_ACCESS_KEY: SecretStr

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "SSM_ACCESS_KEY_ID": "my_access_key_id",
                    "SSM_ENDPOINT": "https://my_ssm_endpoint.com",
                    "SSM_REGION_NAME": "us-east-1",
                    "SSM_SECRET_ACCESS_KEY": "my_secret_access_key",
                }
            ],
        }
    )
