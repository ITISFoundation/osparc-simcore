import datetime
from functools import cached_property
from typing import Optional, cast

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from models_library.docker import DockerLabelKey
from pydantic import Field, PositiveInt, parse_obj_as, validator
from settings_library.base import BaseCustomSettings
from settings_library.rabbit import RabbitSettings
from settings_library.utils_logging import MixinLoggingSettings
from types_aiobotocore_ec2.literals import InstanceTypeType

from .._meta import API_VERSION, API_VTAG, APP_NAME


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: Optional[str] = Field(
        default=None, description="do not define if using standard AWS"
    )
    EC2_REGION_NAME: str = "us-east-1"
    EC2_SECRET_ACCESS_KEY: str


class EC2InstancesSettings(BaseCustomSettings):
    EC2_INSTANCES_ALLOWED_TYPES: list[str] = Field(
        ...,
        min_items=1,
        unique_items=True,
        description="Defines which EC2 instances are considered as candidates for new EC2 instance",
    )
    EC2_INSTANCES_AMI_ID: str = Field(
        ...,
        min_length=1,
        description="Defines the AMI (Amazon Machine Image) ID used to start a new EC2 instance",
    )
    EC2_INSTANCES_MAX_INSTANCES: int = Field(
        default=10,
        description="Defines the maximum number of instances the autoscaling app may create",
    )
    EC2_INSTANCES_SECURITY_GROUP_IDS: list[str] = Field(
        ...,
        min_items=1,
        description="A security group acts as a virtual firewall for your EC2 instances to control incoming and outgoing traffic"
        " (https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-security-groups.html), "
        " this is required to start a new EC2 instance",
    )
    EC2_INSTANCES_SUBNET_ID: str = Field(
        ...,
        min_length=1,
        description="A subnet is a range of IP addresses in your VPC "
        " (https://docs.aws.amazon.com/vpc/latest/userguide/configure-subnets.html), "
        "this is required to start a new EC2 instance",
    )
    EC2_INSTANCES_KEY_NAME: str = Field(
        ...,
        min_length=1,
        description="SSH key filename (without ext) to access the instance through SSH"
        " (https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html),"
        "this is required to start a new EC2 instance",
    )

    EC2_INSTANCES_TIME_BEFORE_TERMINATION: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=55),
        description="Time after which an EC2 instance may be terminated (repeat every hour, min 0, max 59 minutes)",
    )

    @validator("EC2_INSTANCES_TIME_BEFORE_TERMINATION")
    @classmethod
    def ensure_time_is_in_range(cls, value):
        if value < datetime.timedelta(minutes=0):
            value = datetime.timedelta(minutes=0)
        elif value > datetime.timedelta(minutes=59):
            value = datetime.timedelta(minutes=59)
        return value

    @validator("EC2_INSTANCES_ALLOWED_TYPES")
    @classmethod
    def check_valid_intance_names(cls, value):
        # NOTE: needed because of a flaw in BaseCustomSettings
        # issubclass raises TypeError if used on Aliases
        parse_obj_as(tuple[InstanceTypeType, ...], value)
        return value


class NodesMonitoringSettings(BaseCustomSettings):
    NODES_MONITORING_NODE_LABELS: list[DockerLabelKey] = Field(
        default_factory=list,
        description="autoscaling will only monitor nodes with the given labels (if empty all nodes will be monitored), these labels will be added to the new created nodes by default",
    )

    NODES_MONITORING_SERVICE_LABELS: list[DockerLabelKey] = Field(
        default_factory=list,
        description="autoscaling will only monitor services with the given labels (if empty all services will be monitored)",
    )

    NODES_MONITORING_NEW_NODES_LABELS: list[DockerLabelKey] = Field(
        default=["io.simcore.autoscaled-node"],
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

    AUTOSCALING_RABBITMQ: Optional[RabbitSettings] = Field(auto_default_from_env=True)

    @cached_property
    def LOG_LEVEL(self):
        return self.AUTOSCALING_LOGLEVEL

    @validator("AUTOSCALING_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))
