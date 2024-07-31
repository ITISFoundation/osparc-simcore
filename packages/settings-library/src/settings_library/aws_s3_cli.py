from pydantic import Field

from .base import BaseCustomSettings
from .s3 import S3Settings


class AwsS3CliSettings(BaseCustomSettings):
    AWS_S3_CLI_S3: S3Settings | None = Field(
        default=None,
        description="These settings intentionally do not use auto_default_from_env=True because we might want to turn them off if RClone is enabled.",
    )
