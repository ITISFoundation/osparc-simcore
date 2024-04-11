from typing import Any, ClassVar

from pydantic import Field

from .base import BaseCustomSettings


class S3Settings(BaseCustomSettings):
    S3_ACCESS_KEY: str
    S3_ACCESS_TOKEN: str | None = None
    S3_BUCKET_NAME: str
    S3_ENDPOINT: str | None = Field(
        default=None, description="do not define if using standard AWS"
    )
    S3_REGION: str
    S3_SECRET_KEY: str
    S3_SECURE: bool

    class Config(BaseCustomSettings.Config):
        schema_extra: ClassVar[dict[str, Any]] = {  # type: ignore[misc]
            "examples": [
                {
                    "S3_ACCESS_KEY": "my_access_key_id",
                    "S3_BUCKET_NAME": "some-s3-bucket",
                    "S3_ENDPOINT": "https://my_s3_endpoint.com",
                    "S3_REGION": "us-east-1",
                    "S3_SECRET_KEY": "my_secret_access_key",
                    "S3_SECURE": "true",
                },
                {
                    "S3_ACCESS_KEY": "my_access_key_id",
                    "S3_BUCKET_NAME": "some-s3-bucket",
                    "S3_REGION": "us-east-2",
                    "S3_SECRET_KEY": "my_secret_access_key",
                    "S3_SECURE": "true",
                },
            ],
        }
