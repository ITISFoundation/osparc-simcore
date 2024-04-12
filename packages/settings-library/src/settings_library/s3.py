from typing import Any, ClassVar

from pydantic import AnyHttpUrl, Field

from .base import BaseCustomSettings


class S3Settings(BaseCustomSettings):
    S3_ACCESS_KEY: str = Field(min_items=1)
    S3_ACCESS_TOKEN: str | None = Field(default=None, min_items=1)
    S3_BUCKET_NAME: str = Field(min_items=1)
    S3_ENDPOINT: AnyHttpUrl | None = Field(
        default=None, description="do not define if using standard AWS"
    )
    S3_REGION: str = Field(min_items=1)
    S3_SECRET_KEY: str = Field(min_items=1)

    class Config(BaseCustomSettings.Config):
        schema_extra: ClassVar[dict[str, Any]] = {  # type: ignore[misc]
            "examples": [
                {
                    # non AWS use-case
                    "S3_ACCESS_KEY": "my_access_key_id",
                    "S3_BUCKET_NAME": "some-s3-bucket",
                    "S3_ENDPOINT": "https://non-aws-s3_endpoint.com",
                    "S3_REGION": "us-east-1",
                    "S3_SECRET_KEY": "my_secret_access_key",
                },
                {
                    # AWS use-case
                    "S3_ACCESS_KEY": "my_access_key_id",
                    "S3_BUCKET_NAME": "some-s3-bucket",
                    "S3_REGION": "us-east-2",
                    "S3_SECRET_KEY": "my_secret_access_key",
                },
            ],
        }
