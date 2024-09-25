from pydantic import AnyHttpUrl, Field
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: AnyHttpUrl | None = Field(
        default=None, description="do not define if using standard AWS"
    )
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
