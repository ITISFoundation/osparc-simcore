import datetime
from functools import cached_property
from typing import cast

from fastapi import FastAPI
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    VersionTag,
)
from pydantic import Field, NonNegativeInt, PositiveInt, parse_obj_as, validator
from settings_library.base import BaseCustomSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.utils_logging import MixinLoggingSettings
from types_aiobotocore_ec2.literals import InstanceTypeType

from .._meta import API_VERSION, API_VTAG, APP_NAME


class EC2Settings(BaseCustomSettings):
    EC2_ACCESS_KEY_ID: str
    EC2_ENDPOINT: str | None = Field(
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
        description="Defines the maximum number of instances the clusters_keeper app may create",
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

    EC2_INSTANCES_MAX_START_TIME: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=3),
        description="Usual time taken an EC2 instance with the given AMI takes to be in 'running' mode",
    )

    EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS: list[str] = Field(
        default_factory=list,
        description="script(s) to run on EC2 instance startup (be careful!), each entry is run one after the other using '&&' operator",
    )

    @validator("EC2_INSTANCES_ALLOWED_TYPES")
    @classmethod
    def check_valid_intance_names(cls, value):
        # NOTE: needed because of a flaw in BaseCustomSettings
        # issubclass raises TypeError if used on Aliases
        parse_obj_as(tuple[InstanceTypeType, ...], value)
        return value


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: str | None = None
    SC_BUILD_TARGET: BuildTargetEnum | None = None
    SC_VCS_REF: str | None = None
    SC_VCS_URL: str | None = None

    # @Dockerfile
    SC_BOOT_MODE: BootModeEnum | None = None
    SC_BOOT_TARGET: BuildTargetEnum | None = None
    SC_HEALTHCHECK_TIMEOUT: PositiveInt | None = Field(
        None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: int | None = None
    SC_USER_NAME: str | None = None

    # RUNTIME  -----------------------------------------------------------
    CLUSTERS_KEEPER_DEBUG: bool = Field(
        default=False, description="Debug mode", env=["CLUSTERS_KEEPER_DEBUG", "DEBUG"]
    )

    CLUSTERS_KEEPER_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO, env=["CLUSTERS_KEEPER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    CLUSTERS_KEEPER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "CLUSTERS_KEEPER_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    CLUSTERS_KEEPER_EC2_ACCESS: EC2Settings | None = Field(auto_default_from_env=True)

    CLUSTERS_KEEPER_EC2_INSTANCES: EC2InstancesSettings | None = Field(
        auto_default_from_env=True
    )

    CLUSTERS_KEEPER_RABBITMQ: RabbitSettings | None = Field(auto_default_from_env=True)

    CLUSTERS_KEEPER_REDIS: RedisSettings = Field(auto_default_from_env=True)

    CLUSTERS_KEEPER_REGISTRY: RegistrySettings | None = Field(
        auto_default_from_env=True
    )

    CLUSTERS_KEEPER_CLEAN_INTERVAL: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=60),
        description="interval between each clusters clean check (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    SERVICE_TRACKING_HEARTBEAT: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=60),
        description="Service heartbeat interval (everytime a heartbeat is sent into RabbitMQ)",
    )

    CLUSTERS_KEEPER_MAX_MISSED_HEARTBEATS_BEFORE_CLUSTER_TERMINATION: NonNegativeInt = Field(
        default=5,
        description="Max number of missed heartbeats before a cluster is terminated",
    )

    @cached_property
    def LOG_LEVEL(self):  # noqa: N802
        return self.CLUSTERS_KEEPER_LOGLEVEL

    @validator("CLUSTERS_KEEPER_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
