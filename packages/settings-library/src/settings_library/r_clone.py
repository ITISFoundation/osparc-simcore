from enum import StrEnum

from pydantic import Field, NonNegativeInt

from .base import BaseCustomSettings
from .s3 import S3Settings


class S3Provider(StrEnum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneSettings(BaseCustomSettings):
    R_CLONE_S3: S3Settings = Field(auto_default_from_env=True)
    R_CLONE_PROVIDER: S3Provider

    # SEE https://rclone.org/docs/#transfers-n
    R_CLONE_OPTION_TRANSFERS: NonNegativeInt = Field(
        default=5, description="`--transfers X`: sets the amount of parallel transfers"
    )
    # SEE https://rclone.org/docs/#retries-int
    R_CLONE_OPTION_RETRIES: NonNegativeInt = Field(
        default=3, description="`--retries X`: times to retry each individual transfer"
    )
    # SEE https://rclone.org/docs/#buffer-size-size
    R_CLONE_OPTION_BUFFER_SIZE: str = Field(
        default="0M",
        description="`--buffer-size X`: sets the amount of RAM to use for each individual transfer",
    )
