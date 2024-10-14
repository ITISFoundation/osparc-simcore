from typing import Annotated

from common_library.pydantic_basic_types import IDStr
from pydantic import AnyHttpUrl, BeforeValidator, Field, TypeAdapter
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings

ANY_HTTP_URL_ADAPTER: TypeAdapter = TypeAdapter(AnyHttpUrl)


class S3Settings(BaseCustomSettings):
    S3_ACCESS_KEY: IDStr
    S3_BUCKET_NAME: IDStr
    S3_ENDPOINT: Annotated[
        str, BeforeValidator(lambda x: str(ANY_HTTP_URL_ADAPTER.validate_python(x)))
    ] | None = Field(default=None, description="do not define if using standard AWS")
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
