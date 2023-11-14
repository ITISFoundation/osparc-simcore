from typing import Any, ClassVar

from pydantic import Field

from .base import BaseCustomSettings


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: str | None = Field(
        default=None, description="do not define if using standard AWS"
    )
    EC2_REGION_NAME: str = "us-east-1"
    EC2_SECRET_ACCESS_KEY: str

    class Config(BaseCustomSettings.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "EC2_ACCESS_KEY_ID": "my_access_key_id",
                    "EC2_ENDPOINT": "http://my_ec2_endpoint.com",
                    "EC2_REGION_NAME": "us-east-1",
                    "EC2_SECRET_ACCESS_KEY": "my_secret_access_key",
                }
            ],
        }
