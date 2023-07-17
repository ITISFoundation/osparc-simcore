from enum import Enum

from pydantic import Field

from .base import BaseCustomSettings
from .s3 import S3Settings


class S3Provider(str, Enum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class RCloneSettings(BaseCustomSettings):
    # TODO: PC this flag is actually ONLY used by the dynamic sidecar.
    # It determines how the dynamic sidecar sets up node-ports storage
    # mechanism. I propose it is added as an extra independent variable in
    # simcore_service_dynamic_idecar.core.settings.Settings instead of here.
    R_CLONE_ENABLED: bool = Field(
        default=True,
        description=(
            "simple way to enable/disable the usage of rclone "
            "in parts of the system where it is optional "
            "eg: dynamic-sidecar"
        ),
    )
    R_CLONE_S3: S3Settings = Field(auto_default_from_env=True)
    R_CLONE_PROVIDER: S3Provider
