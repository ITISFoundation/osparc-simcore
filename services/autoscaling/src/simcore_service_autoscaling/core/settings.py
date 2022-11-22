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


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: Optional[str] = Field(
        default=None, description="do not define if using standard AWS"
    )
    EC2_REGION_NAME: str = "us-east-1"
    EC2_SECRET_ACCESS_KEY: str


class EC2InstancesSettings(BaseCustomSettings):
    EC2_INSTANCES_ALLOWED_TYPES: tuple[str, ...] = Field(
        ...,
        description="Defines which EC2 instances are considered as candidates for new docker nodes",
    )
    EC2_INSTANCES_AMI_ID: str = Field(
        ..., description="Defines the AMI ID used to initialize a new docker node"
    )
    EC2_INSTANCES_MAX_INSTANCES: int = Field(
        10,
        description="Defines the maximum number of instances the autoscaling app may create",
    )
    EC2_INSTANCES_SECURITY_GROUP_IDS: list[str] = Field(
        ..., description="TO BE DEFINED"
    )
    EC2_INSTANCES_SUBNET_ID: str = Field(..., description="TO BE DEFINED")
    EC2_INSTANCES_KEY_NAME: str = Field(
        ...,
        description="SSH key filename (without ext) to access the docker swarm manager",
    )


class NodesMonitoringSettings(BaseCustomSettings):
    NODES_MONITORING_NODE_LABELS: list[str] = Field(
        default_factory=list,
        description="autoscaling will only monitor nodes with the given labels (if empty all nodes will be monitored)",
    )

    NODES_MONITORING_SERVICE_LABELS: list[str] = Field(
        default_factory=list,
        description="autoscaling will only monitor services with the given labels (if empty all services will be monitored)",
    )

    NODES_MONITORING_SERVICE_IMAGE_NAMES: list[str] = Field(
        default_factory=list,
        description="autoscaling will only monitor services with the given image names (if empty all services will be monitored)",
    )

    NODES_MONITORING_NEW_NODES_LABELS: list[str] = Field(
        default_factory=list,
        description="autoscaling will add these labels to any new node it creates (additional to the ones in NODES_MONITORING_NODE_LABELS",
    )


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

    AUTOSCALING_EC2_ACCESS: Optional[EC2Settings] = Field(auto_default_from_env=True)

    AUTOSCALING_EC2_INSTANCES: Optional[EC2InstancesSettings] = Field(
        auto_default_from_env=True
    )

    AUTOSCALING_NODES_MONITORING: Optional[NodesMonitoringSettings] = Field(
        auto_default_from_env=True
    )

    AUTOSCALING_POLL_INTERVAL: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=10),
        description="interval between each resource check (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    @cached_property
    def LOG_LEVEL(self):
        return self.AUTOSCALING_LOGLEVEL

    @validator("AUTOSCALING_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))
