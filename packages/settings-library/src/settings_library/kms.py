from typing import Annotated

from pydantic import BeforeValidator, Field, SecretStr
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .utils_validators import validate_nullable_url


class KMSSettings(BaseCustomSettings):
    KMS_KEY_ID: Annotated[
        str,
        Field(description="AWS KMS key id, alias or ARN used to encrypt/decrypt job root keys"),
    ]
    KMS_ACCESS_KEY_ID: Annotated[
        SecretStr | None,
        Field(description="do not define if relying on the default AWS credentials chain (e.g. IAM role)"),
    ] = None
    KMS_ENDPOINT: Annotated[
        str | None,
        BeforeValidator(validate_nullable_url),
        Field(description="do not define if using standard AWS"),
    ] = None
    KMS_REGION_NAME: str = "us-east-1"
    KMS_SECRET_ACCESS_KEY: Annotated[
        SecretStr | None,
        Field(description="do not define if relying on the default AWS credentials chain (e.g. IAM role)"),
    ] = None

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "KMS_KEY_ID": "arn:aws:kms:us-east-1:123456789012:key/1234abcd-12ab-34cd-56ef-1234567890ab",
                    "KMS_REGION_NAME": "us-east-1",
                },
                {
                    "KMS_ACCESS_KEY_ID": "my_access_key_id",
                    "KMS_ENDPOINT": "https://my_kms_endpoint.com",
                    "KMS_KEY_ID": "alias/my-key",
                    "KMS_REGION_NAME": "us-east-1",
                    "KMS_SECRET_ACCESS_KEY": "my_secret_access_key",
                },
            ],
        }
    )
