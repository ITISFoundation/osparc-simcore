import datetime
from functools import cached_property
from typing import Any, ClassVar, Final, cast

from aws_library.ec2.models import EC2InstanceBootSpecific, EC2Tags
from fastapi import FastAPI
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from models_library.clusters import InternalClusterAuthentication
from models_library.docker import DockerLabelKey
from pydantic import (
    AnyUrl,
    Field,
    NonNegativeInt,
    PositiveInt,
    parse_obj_as,
    root_validator,
    validator,
)
from settings_library.base import BaseCustomSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.ec2 import EC2Settings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.utils_logging import MixinLoggingSettings
from types_aiobotocore_ec2.literals import InstanceTypeType

from .._meta import API_VERSION, API_VTAG, APP_NAME

AUTOSCALING_ENV_PREFIX: Final[str] = "AUTOSCALING_"


class AutoscalingEC2Settings(EC2Settings):
    class Config(EC2Settings.Config):
        env_prefix = AUTOSCALING_ENV_PREFIX

        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    f"{AUTOSCALING_ENV_PREFIX}EC2_ACCESS_KEY_ID": "my_access_key_id",
                    f"{AUTOSCALING_ENV_PREFIX}EC2_ENDPOINT": "https://my_ec2_endpoint.com",
                    f"{AUTOSCALING_ENV_PREFIX}EC2_REGION_NAME": "us-east-1",
                    f"{AUTOSCALING_ENV_PREFIX}EC2_SECRET_ACCESS_KEY": "my_secret_access_key",
                }
            ],
        }


class EC2InstancesSettings(BaseCustomSettings):
    EC2_INSTANCES_ALLOWED_TYPES: dict[str, EC2InstanceBootSpecific] = Field(
        ...,
        description="Defines which EC2 instances are considered as candidates for new EC2 instance and their respective boot specific parameters",
    )

    EC2_INSTANCES_KEY_NAME: str = Field(
        ...,
        min_length=1,
        description="SSH key filename (without ext) to access the instance through SSH"
        " (https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html),"
        "this is required to start a new EC2 instance",
    )
    EC2_INSTANCES_MACHINES_BUFFER: NonNegativeInt = Field(
        default=0,
        description="Constant reserve of drained ready machines for fast(er) usage,"
        "disabled when set to 0. Uses 1st machine defined in EC2_INSTANCES_ALLOWED_TYPES",
    )
    EC2_INSTANCES_MAX_INSTANCES: int = Field(
        default=10,
        description="Defines the maximum number of instances the autoscaling app may create",
    )
    EC2_INSTANCES_MAX_START_TIME: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=1),
        description="Usual time taken an EC2 instance with the given AMI takes to be in 'running' mode "
        "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )
    EC2_INSTANCES_NAME_PREFIX: str = Field(
        default="autoscaling",
        min_length=1,
        description="prefix used to name the EC2 instances created by this instance of autoscaling",
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
    EC2_INSTANCES_TIME_BEFORE_TERMINATION: datetime.timedelta = Field(
        default=datetime.timedelta(minutes=1),
        description="Time after which an EC2 instance may be terminated (0<=T<=59 minutes, is automatically capped)"
        "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )
    EC2_INSTANCES_CUSTOM_TAGS: EC2Tags = Field(
        ...,
        description="Allows to define tags that should be added to the created EC2 instance default tags. "
        "a tag must have a key and an optional value. see [https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Using_Tags.html]",
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
    def check_valid_instance_names(
        cls, value: dict[str, EC2InstanceBootSpecific]
    ) -> dict[str, EC2InstanceBootSpecific]:
        # NOTE: needed because of a flaw in BaseCustomSettings
        # issubclass raises TypeError if used on Aliases
        if all(parse_obj_as(InstanceTypeType, key) for key in value):
            return value

        msg = "Invalid instance type name"
        raise ValueError(msg)


class NodesMonitoringSettings(BaseCustomSettings):
    NODES_MONITORING_NODE_LABELS: list[DockerLabelKey] = Field(
        ...,
        description="autoscaling will only monitor nodes with the given labels (if empty all nodes will be monitored), these labels will be added to the new created nodes by default",
    )

    NODES_MONITORING_SERVICE_LABELS: list[DockerLabelKey] = Field(
        ...,
        description="autoscaling will only monitor services with the given labels (if empty all services will be monitored)",
    )

    NODES_MONITORING_NEW_NODES_LABELS: list[DockerLabelKey] = Field(
        ...,
        description="autoscaling will add these labels to any new node it creates (additional to the ones in NODES_MONITORING_NODE_LABELS",
    )


class DaskMonitoringSettings(BaseCustomSettings):
    DASK_MONITORING_URL: AnyUrl = Field(
        ..., description="the url to the osparc-dask-scheduler"
    )
    DASK_SCHEDULER_AUTH: InternalClusterAuthentication = Field(
        ...,
        description="defines the authentication of the clusters created via clusters-keeper (can be None or TLS)",
    )


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
    AUTOSCALING_DEBUG: bool = Field(
        default=False, description="Debug mode", env=["AUTOSCALING_DEBUG", "DEBUG"]
    )
    AUTOSCALING_REMOTE_DEBUG_PORT: PortInt = PortInt(3000)

    AUTOSCALING_LOGLEVEL: LogLevel = Field(
        LogLevel.INFO, env=["AUTOSCALING_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )
    AUTOSCALING_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "AUTOSCALING_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )

    AUTOSCALING_EC2_ACCESS: AutoscalingEC2Settings | None = Field(
        auto_default_from_env=True
    )

    AUTOSCALING_EC2_INSTANCES: EC2InstancesSettings | None = Field(
        auto_default_from_env=True
    )

    AUTOSCALING_NODES_MONITORING: NodesMonitoringSettings | None = Field(
        auto_default_from_env=True
    )

    AUTOSCALING_POLL_INTERVAL: datetime.timedelta = Field(
        default=datetime.timedelta(seconds=10),
        description="interval between each resource check "
        "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    AUTOSCALING_RABBITMQ: RabbitSettings | None = Field(auto_default_from_env=True)

    AUTOSCALING_REDIS: RedisSettings = Field(auto_default_from_env=True)

    AUTOSCALING_REGISTRY: RegistrySettings | None = Field(auto_default_from_env=True)

    AUTOSCALING_DASK: DaskMonitoringSettings | None = Field(auto_default_from_env=True)

    AUTOSCALING_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True

    AUTOSCALING_DRAIN_NODES_WITH_LABELS: bool = Field(
        default=False,
        description="If true, drained nodes"
        " are maintained as active (in the docker terminology) "
        "but a docker node label named osparc-services-ready is attached",
    )

    @cached_property
    def LOG_LEVEL(self):  # noqa: N802
        return self.AUTOSCALING_LOGLEVEL

    @validator("AUTOSCALING_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value: str) -> str:
        # NOTE: mypy is not happy without the cast
        return cast(str, cls.validate_log_level(value))

    @root_validator()
    @classmethod
    def exclude_both_dynamic_computational_mode(cls, values):
        if (
            values.get("AUTOSCALING_DASK") is not None
            and values.get("AUTOSCALING_NODES_MONITORING") is not None
        ):
            msg = "Autoscaling cannot be set to monitor both computational and dynamic services (both AUTOSCALING_DASK and AUTOSCALING_NODES_MONITORING are currently set!)"
            raise ValueError(msg)
        return values


def get_application_settings(app: FastAPI) -> ApplicationSettings:
    return cast(ApplicationSettings, app.state.settings)
