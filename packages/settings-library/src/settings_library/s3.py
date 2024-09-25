from pydantic import AnyHttpUrl, Field
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .basic_types import IDStr


class S3Settings(BaseCustomSettings):
    S3_ACCESS_KEY: IDStr
    S3_BUCKET_NAME: IDStr
    S3_ENDPOINT: AnyHttpUrl | None = Field(
        default=None, description="do not define if using standard AWS"
    )
    S3_REGION: IDStr
    S3_SECRET_KEY: IDStr

    model_config = SettingsConfigDict(
        json_schema_extra={
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
    )
