import datetime
from functools import cached_property
from typing import Optional, cast

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from pydantic import Field, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.utils_logging import MixinLoggingSettings

from .._meta import API_VERSION, API_VTAG, APP_NAME


class AwsSettings(BaseCustomSettings):
    # AWS Access
    AWS_ACCESS_KEY_ID: str
    AWS_ENDPOINT: Optional[str] = Field(
        default=None, description="do not define if using standard AWS"
    )
    AWS_REGION_NAME: str = "us-east-1"
    AWS_SECRET_ACCESS_KEY: str

    # Cluster
    AWS_DNS: str = Field(..., description="DNS Name of the docker swarm manager")
    AWS_KEY_NAME: str = Field(
        ...,
        description="SSH key filename (without ext) to access the docker swarm manager",
    )

    # EC2 instance paramaters
    AWS_ALLOWED_EC2_INSTANCE_TYPE_NAMES: tuple[str, ...] = Field(
        ...,
        description="Defines which EC2 instances are considered as candidates for new docker nodes",
    )
    AWS_AMI_ID: str = Field(
        ..., description="Defines the AMI ID used to initialize a new docker node"
    )
    AWS_MAX_NUMBER_OF_INSTANCES: int = Field(
        10,
        description="Defines the maximum number of instances the autoscaling app may create",
    )
    AWS_SECURITY_GROUP_IDS: list[str] = Field(..., description="TO BE DEFINED")
    AWS_SUBNET_ID: str = Field(..., description="TO BE DEFINED")


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: Optional[str] = None
    SC_BUILD_TARGET: Optional[BuildTargetEnum] = None
    SC_VCS_REF: Optional[str] = None
    SC_VCS_URL: Optional[str] = None

    # @Dockerfile
    SC_BOOT_MODE: Optional[BootModeEnum] = None
    SC_BOOT_TARGET: Optional[BuildTargetEnum] = None
    SC_HEALTHCHECK_TIMEOUT: Optional[PositiveInt] = Field(
        None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: Optional[int] = None
    SC_USER_NAME: Optional[str] = None

    # RUNTIME  -----------------------------------------------------------
    AUTOSCALING_DEBUG: bool = Field(
        False, description="Debug mode", env=["AUTOSCALING_DEBUG", "DEBUG"]
    )

    AUTOSCALING_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO, env=["AUTOSCALING_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    AUTOSCALING_AWS: Optional[AwsSettings] = Field(auto_default_from_env=True)

    AUTOSCALING_POLL_INTERVAL: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=10),
        description="interval between each resource check (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    AUTOSCALING_MONITORED_NODES_LABELS: list[str] = Field(
        default_factory=list,
        description="autoscaling will only monitor nodes with the given labels (if empty all nodes will be monitored)",
    )

    AUTOSCALING_MONITORED_SERVICES_LABELS: list[str] = Field(
        default_factory=list,
        description="autoscaling will only monitor services with the given labels (if empty all services will be monitored)",
    )

    AUTOSCALING_MONITORED_SERVICES_IMAGE_NAMES: list[str] = Field(
        default_factory=list,
        description="autoscaling will only monitor services with the given image names (if empty all services will be monitored)",
    )

    @cached_property
    def LOG_LEVEL(self):
        return self.AUTOSCALING_LOGLEVEL

    @validator("AUTOSCALING_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))
