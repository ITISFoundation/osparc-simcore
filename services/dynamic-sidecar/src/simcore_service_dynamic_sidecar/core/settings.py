import warnings
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import cast

from models_library.basic_types import BootModeEnum, PortInt
from models_library.callbacks_mapping import CallbacksMapping
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import DynamicServiceKey, RunID, ServiceVersion
from models_library.users import UserID
from pydantic import ByteSize, Field, PositiveInt, parse_obj_as, validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.base import BaseCustomSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.node_ports import StorageAuthSettings
from settings_library.postgres import PostgresSettings
from settings_library.r_clone import RCloneSettings
from settings_library.rabbit import RabbitSettings
from settings_library.resource_usage_tracker import (
    DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
)
from settings_library.utils_logging import MixinLoggingSettings


class ResourceTrackingSettings(BaseCustomSettings):
    RESOURCE_TRACKING_HEARTBEAT_INTERVAL: timedelta = Field(
        default=DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
        description="each time the status of the service is propagated",
    )


class SystemMonitorSettings(BaseCustomSettings):
    DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE: bool = Field(
        default=False, description="enabled/disabled disk usage monitoring"
    )


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    SC_BOOT_MODE: BootModeEnum = Field(
        ...,
        description="boot mode helps determine if in development mode or normal operation",
    )

    DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR: Path = Field(
        ...,
        description="Base directory where dynamic-sidecar stores creates "
        "and shares volumes between itself and the spawned containers. "
        "It is used as a mount directory for the director-v2."
        "Sidecar must have r/w permissions in this folder.",
    )

    DYNAMIC_SIDECAR_SHARED_STORE_DIR: Path = Field(
        ...,
        description="Directory where the dynamic-sidecar persists "
        "it's SharedStore data. This is used in case of reboots of the "
        "container to reload recover the state of the store.",
    )

    # LOGGING
    LOG_LEVEL: str = Field(
        default="WARNING", env=["DYNAMIC_SIDECAR_LOG_LEVEL", "LOG_LEVEL", "LOGLEVEL"]
    )

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    DYNAMIC_SIDECAR_PORT: PortInt = Field(
        default=8000, description="port where the server will be currently serving"
    )

    DYNAMIC_SIDECAR_COMPOSE_NAMESPACE: str = Field(
        ...,
        description=(
            "To avoid collisions when scheduling on the same node, this "
            "will be composed by the project_uuid and node_uuid."
        ),
    )

    DYNAMIC_SIDECAR_MAX_COMBINED_CONTAINER_NAME_LENGTH: PositiveInt = Field(
        default=63, description="the container name which will be used as hostname"
    )

    DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT: PositiveInt = Field(
        default=5,
        description=(
            "When receiving SIGTERM the process has 10 seconds to cleanup its children "
            "forcing our children to stop in 5 seconds in all cases"
        ),
    )

    DYNAMIC_SIDECAR_TELEMETRY_DISK_USAGE_MONITOR_INTERVAL: timedelta = Field(
        default=timedelta(seconds=5),
        description="time between checks for disk usage",
    )

    DEBUG: bool = Field(
        default=False,
        description="If set to True the application will boot into debug mode",
    )

    DYNAMIC_SIDECAR_RESERVED_SPACE_SIZE: ByteSize = Field(
        parse_obj_as(ByteSize, "10Mib"),
        description=(
            "Disk space reserve when the dy-sidecar is started. Can be freed at "
            "any time via an API call. Main reason to free this disk space is "
            "when the host's `/docker` partition has reached 0. Services will "
            "behave unexpectedly until some disk space is freed. This will "
            "allow to manual intervene and cleanup."
        ),
    )

    DY_SIDECAR_CALLBACKS_MAPPING: CallbacksMapping = Field(
        ..., description="callbacks to use for this service"
    )
    DY_SIDECAR_PATH_INPUTS: Path = Field(
        ..., description="path where to expect the inputs folder"
    )
    DY_SIDECAR_PATH_OUTPUTS: Path = Field(
        ..., description="path where to expect the outputs folder"
    )
    DY_SIDECAR_STATE_PATHS: list[Path] = Field(
        ..., description="list of additional paths to be synced"
    )
    DY_SIDECAR_USER_PREFERENCES_PATH: Path | None = Field(
        None, description="path where the user preferences should be saved"
    )
    DY_SIDECAR_STATE_EXCLUDE: set[str] = Field(
        ..., description="list of patterns to exclude files when saving states"
    )
    DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=["DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DY_SIDECAR_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default={},
        env=["DY_SIDECAR_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )
    DY_SIDECAR_USER_ID: UserID
    DY_SIDECAR_PROJECT_ID: ProjectID
    DY_SIDECAR_NODE_ID: NodeID
    DY_SIDECAR_RUN_ID: RunID
    DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS: bool

    DY_SIDECAR_SERVICE_KEY: DynamicServiceKey | None = None
    DY_SIDECAR_SERVICE_VERSION: ServiceVersion | None = None
    DY_SIDECAR_PRODUCT_NAME: ProductName | None = None

    NODE_PORTS_STORAGE_AUTH: StorageAuthSettings | None = Field(
        auto_default_from_env=True
    )
    DY_SIDECAR_R_CLONE_SETTINGS: RCloneSettings = Field(auto_default_from_env=True)
    DY_SIDECAR_AWS_S3_CLI_SETTINGS: AwsS3CliSettings | None = Field(
        None,
        description="AWS S3 settings are used for the AWS S3 CLI. If these settings are filled, the AWS S3 CLI is used instead of RClone.",
    )
    POSTGRES_SETTINGS: PostgresSettings = Field(auto_default_from_env=True)
    RABBIT_SETTINGS: RabbitSettings = Field(auto_default_from_env=True)

    DY_DEPLOYMENT_REGISTRY_SETTINGS: RegistrySettings = Field()
    DY_DOCKER_HUB_REGISTRY_SETTINGS: RegistrySettings | None = Field()

    RESOURCE_TRACKING: ResourceTrackingSettings = Field(auto_default_from_env=True)

    SYSTEM_MONITOR_SETTINGS: SystemMonitorSettings = Field(auto_default_from_env=True)

    @property
    def are_prometheus_metrics_enabled(self) -> bool:
        return self.DY_SIDECAR_CALLBACKS_MAPPING.metrics is not None

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)


@lru_cache
def get_settings() -> ApplicationSettings:
    """used outside the context of a request"""
    warnings.warn("Use instead app.state.settings", DeprecationWarning, stacklevel=2)
    return cast(ApplicationSettings, ApplicationSettings.create_from_envs())
