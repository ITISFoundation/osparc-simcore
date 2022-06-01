from enum import Enum

from pydantic import Field

from .base import BaseCustomSettings
from .s3 import S3Settings


class S3Provider(str, Enum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneSettings(BaseCustomSettings):
    R_CLONE_ENABLED: bool = Field(
        False,  # NOTE: feature is still experimental disabling by default
        description=(
            "simple way to enable/disable the usage of rclone "
            "in parts of the system where it is optional "
            "eg: dynamic-sidecar"
        ),
    )
    R_CLONE_S3: S3Settings = Field(auto_default_from_env=True)
    R_CLONE_PROVIDER: S3Provider
