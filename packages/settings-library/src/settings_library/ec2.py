from typing import Annotated

from pydantic import BeforeValidator, Field
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .utils_validators import validate_nullable_url


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: Annotated[
        str | None,
        BeforeValidator(validate_nullable_url),
        Field(description="do not define if using standard AWS"),
    ] = None
    EC2_REGION_NAME: str = "us-east-1"
    EC2_SECRET_ACCESS_KEY: str

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "EC2_ACCESS_KEY_ID": "my_access_key_id",
                    "EC2_ENDPOINT": "https://my_ec2_endpoint.com",
                    "EC2_REGION_NAME": "us-east-1",
                    "EC2_SECRET_ACCESS_KEY": "my_secret_access_key",
                }
            ],
        }
    )
