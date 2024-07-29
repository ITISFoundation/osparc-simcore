from pydantic import Field

from .base import BaseCustomSettings
from .r_clone import S3Provider
from .s3 import S3Settings


class AwsS3CliSettings(BaseCustomSettings):
    AWS_S3_CLI_S3: S3Settings = Field(auto_default_from_env=True)
    AWS_S3_CLI_PROVIDER: S3Provider
