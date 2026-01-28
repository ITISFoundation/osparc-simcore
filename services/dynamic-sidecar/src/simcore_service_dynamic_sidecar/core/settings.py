import warnings
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Annotated, cast

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from models_library.basic_types import PortInt
from models_library.callbacks_mapping import CallbacksMapping
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import LegacyState
from models_library.services import DynamicServiceKey, ServiceRunID, ServiceVersion
from models_library.users import UserID
from pydantic import (
    AliasChoices,
    ByteSize,
    Field,
    PositiveInt,
    TypeAdapter,
    field_validator,
)
from settings_library.application import BaseApplicationSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.node_ports import StorageAuthSettings
from settings_library.postgres import PostgresSettings
from settings_library.r_clone import RCloneSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.resource_usage_tracker import (
    DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
)
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings


class ResourceTrackingSettings(BaseApplicationSettings):
    RESOURCE_TRACKING_HEARTBEAT_INTERVAL: Annotated[
        timedelta,
        Field(
            default=DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
            description="each time the status of the service is propagated",
        ),
    ]

    _validate_resource_tracking_heartbeat_interval = validate_numeric_string_as_timedelta(
        "RESOURCE_TRACKING_HEARTBEAT_INTERVAL"
    )


class SystemMonitorSettings(BaseApplicationSettings):
    DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE: Annotated[
        bool, Field(description="enabled/disabled disk usage monitoring")
    ] = False


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR: Annotated[
        Path,
        Field(
            description="Base directory where dynamic-sidecar stores creates "
            "and shares volumes between itself and the spawned containers. "
            "It is used as a mount directory for the director-v2."
            "Sidecar must have r/w permissions in this folder.",
        ),
    ]

    DYNAMIC_SIDECAR_SHARED_STORE_DIR: Annotated[
        Path,
        Field(
            description="Directory where the dynamic-sidecar persists "
            "it's SharedStore data. This is used in case of reboots of the "
            "container to reload recover the state of the store.",
        ),
    ]

    # LOGGING
    LOG_LEVEL: Annotated[
        str,
        Field(validation_alias=AliasChoices("DYNAMIC_SIDECAR_LOG_LEVEL", "LOG_LEVEL", "LOGLEVEL")),
    ] = "WARNING"

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    DYNAMIC_SIDECAR_PORT: Annotated[PortInt, Field(description="port where the server will be currently serving")] = (
        8000
    )

    DYNAMIC_SIDECAR_COMPOSE_NAMESPACE: Annotated[
        str,
        Field(
            description=(
                "To avoid collisions when scheduling on the same node, this "
                "will be composed by the project_uuid and node_uuid."
            )
        ),
    ]

    DYNAMIC_SIDECAR_MAX_COMBINED_CONTAINER_NAME_LENGTH: Annotated[
        PositiveInt, Field(description="the container name which will be used as hostname")
    ] = 63

    DYNAMIC_SIDECAR_STOP_AND_REMOVE_TIMEOUT: Annotated[
        PositiveInt,
        Field(
            description=(
                "When receiving SIGTERM the process has 10 seconds to cleanup its children "
                "forcing our children to stop in 5 seconds in all cases"
            ),
        ),
    ] = 5

    DYNAMIC_SIDECAR_TELEMETRY_DISK_USAGE_MONITOR_INTERVAL: Annotated[
        timedelta, Field(description="time between checks for disk usage")
    ] = timedelta(seconds=5)

    DEBUG: Annotated[bool, Field(description="If set to True the application will boot into debug mode")] = False

    DYNAMIC_SIDECAR_RESERVED_SPACE_SIZE: Annotated[
        ByteSize,
        Field(
            description=(
                "Disk space reserve when the dy-sidecar is started. Can be freed at "
                "any time via an API call. Main reason to free this disk space is "
                "when the host's `/docker` partition has reached 0. Services will "
                "behave unexpectedly until some disk space is freed. This will "
                "allow to manual intervene and cleanup."
            ),
        ),
    ] = TypeAdapter(ByteSize).validate_python("10Mib")

    DY_SIDECAR_CALLBACKS_MAPPING: Annotated[CallbacksMapping, Field(description="callbacks to use for this service")]
    DY_SIDECAR_PATH_INPUTS: Annotated[Path, Field(description="path where to expect the inputs folder")]
    DY_SIDECAR_PATH_OUTPUTS: Annotated[Path, Field(description="path where to expect the outputs folder")]
    DY_SIDECAR_STATE_PATHS: Annotated[list[Path], Field(description="list of additional paths to be synced")]
    DY_SIDECAR_USER_PREFERENCES_PATH: Annotated[
        Path | None, Field(description="path where the user preferences should be saved")
    ] = None
    DY_SIDECAR_STATE_EXCLUDE: Annotated[
        set[str], Field(description="list of patterns to exclude files when saving states")
    ]
    DY_SIDECAR_LEGACY_STATE: Annotated[
        LegacyState | None, Field(description="used to recover state when upgrading service")
    ] = None
    DY_SIDECAR_REQUIRES_DATA_MOUNTING: Annotated[
        bool, Field(description="indicates whether data mounting is required for this service")
    ] = False

    DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description=(
                "Enables local development log format. "
                "WARNING: make sure it is disabled if you want to have structured logs!"
            ),
        ),
    ] = False
    DY_SIDECAR_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices("DY_SIDECAR_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"),
            description=(
                "is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') "
                "to a list of log message patterns that should be filtered out."
            ),
        ),
    ] = DEFAULT_FACTORY
    DY_SIDECAR_USER_ID: UserID
    DY_SIDECAR_PROJECT_ID: ProjectID
    DY_SIDECAR_NODE_ID: NodeID
    DY_SIDECAR_RUN_ID: ServiceRunID
    DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS: bool

    DY_SIDECAR_SERVICE_KEY: DynamicServiceKey | None = None
    DY_SIDECAR_SERVICE_VERSION: ServiceVersion | None = None
    DY_SIDECAR_PRODUCT_NAME: ProductName | None = None

    NODE_PORTS_STORAGE_AUTH: Annotated[
        StorageAuthSettings | None, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    DY_SIDECAR_R_CLONE_SETTINGS: Annotated[RCloneSettings, Field(json_schema_extra={"auto_default_from_env": True})]
    POSTGRES_SETTINGS: Annotated[PostgresSettings, Field(json_schema_extra={"auto_default_from_env": True})]
    RABBIT_SETTINGS: Annotated[RabbitSettings, Field(json_schema_extra={"auto_default_from_env": True})]
    REDIS_SETTINGS: Annotated[RedisSettings, Field(json_schema_extra={"auto_default_from_env": True})]

    DY_DEPLOYMENT_REGISTRY_SETTINGS: RegistrySettings
    DY_DOCKER_HUB_REGISTRY_SETTINGS: RegistrySettings | None = None

    RESOURCE_TRACKING: Annotated[ResourceTrackingSettings, Field(json_schema_extra={"auto_default_from_env": True})]

    SYSTEM_MONITOR_SETTINGS: Annotated[SystemMonitorSettings, Field(json_schema_extra={"auto_default_from_env": True})]

    DYNAMIC_SIDECAR_TRACING: Annotated[
        TracingSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for opentelemetry tracing",
        ),
    ]

    @property
    def are_prometheus_metrics_enabled(self) -> bool:
        return (  # pylint: disable=no-member
            self.DY_SIDECAR_CALLBACKS_MAPPING.metrics is not None
        )

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        return cls.validate_log_level(value)

    _validate_dynamic_sidecar_telemetry_disk_usage_monitor_interval = validate_numeric_string_as_timedelta(
        "DYNAMIC_SIDECAR_TELEMETRY_DISK_USAGE_MONITOR_INTERVAL"
    )


@lru_cache
def get_settings() -> ApplicationSettings:
    """used outside the context of a request"""
    warnings.warn("Use instead app.state.settings", DeprecationWarning, stacklevel=2)
    return cast(ApplicationSettings, ApplicationSettings.create_from_envs())
