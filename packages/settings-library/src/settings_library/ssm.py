from typing import Annotated

from common_library.pydantic_type_adapters import AnyHttpUrlLegacyAdapter
from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings


class SSMSettings(BaseCustomSettings):
    SSM_ACCESS_KEY_ID: SecretStr
    SSM_ENDPOINT: Annotated[
        str, BeforeValidator(lambda x: str(AnyHttpUrlLegacyAdapter.validate_python(x)))
    ] | None = Field(default=None, description="do not define if using standard AWS")
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
