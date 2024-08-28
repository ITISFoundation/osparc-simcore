from pydantic import AnyHttpUrl, ConfigDict, Field, SecretStr

from .base import BaseCustomSettings


class SSMSettings(BaseCustomSettings):
    SSM_ACCESS_KEY_ID: SecretStr
    SSM_ENDPOINT: AnyHttpUrl | None = Field(
        default=None, description="do not define if using standard AWS"
    )
    SSM_REGION_NAME: str = "us-east-1"
    SSM_SECRET_ACCESS_KEY: SecretStr

    model_config = ConfigDict(
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
