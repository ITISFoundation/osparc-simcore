# pylint: disable=no-self-argument
# pylint: disable=no-self-use


import datetime
from functools import cached_property
from typing import Annotated, cast

from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from fastapi import FastAPI
from models_library.basic_types import LogLevel, PortInt
from models_library.clusters import (
    BaseCluster,
    ClusterAuthentication,
    ClusterTypeInModel,
    NoAuthentication,
)
from pydantic import (
    AliasChoices,
    AnyUrl,
    Field,
    NonNegativeInt,
    PositiveInt,
    field_validator,
)
from settings_library.application import BaseApplicationSettings
from settings_library.base import BaseCustomSettings
from settings_library.catalog import CatalogSettings
from settings_library.director_v0 import DirectorV0Settings
from settings_library.docker_registry import RegistrySettings
from settings_library.http_client_request import ClientRequestSettings
from settings_library.node_ports import (
    NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE,
    StorageAuthSettings,
)
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.resource_usage_tracker import (
    DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
    ResourceUsageTrackerSettings,
)
from settings_library.storage import StorageSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings
from simcore_sdk.node_ports_v2 import FileLinkType

from .dynamic_services_settings import DynamicServicesSettings


class ComputationalBackendSettings(BaseCustomSettings):
    COMPUTATIONAL_BACKEND_ENABLED: bool = True
    COMPUTATIONAL_BACKEND_SCHEDULING_CONCURRENCY: Annotated[
        PositiveInt,
        Field(
            description="defines how many pipelines the application can schedule concurrently"
        ),
    ] = 50
    COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED: bool = True
    COMPUTATIONAL_BACKEND_PER_CLUSTER_MAX_DISTRIBUTED_CONCURRENT_CONNECTIONS: Annotated[
        PositiveInt,
        Field(
            description="defines how many concurrent connections to each dask scheduler are allowed across all director-v2 replicas"
        ),
    ] = 20
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL: Annotated[
        AnyUrl,
        Field(
            description="This is the cluster that will be used by default"
            " when submitting computational services (typically "
            "tcp://dask-scheduler:8786, tls://dask-scheduler:8786 for the internal cluster",
        ),
    ]
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH: Annotated[
        ClusterAuthentication,
        Field(
            description="this is the cluster authentication that will be used by default"
        ),
    ]
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_FILE_LINK_TYPE: Annotated[
        FileLinkType,
        Field(
            description=f"Default file link type to use with the internal cluster '{list(FileLinkType)}'"
        ),
    ] = FileLinkType.S3
    COMPUTATIONAL_BACKEND_DEFAULT_FILE_LINK_TYPE: Annotated[
        FileLinkType,
        Field(
            description=f"Default file link type to use with computational backend '{list(FileLinkType)}'"
        ),
    ] = FileLinkType.PRESIGNED
    COMPUTATIONAL_BACKEND_ON_DEMAND_CLUSTERS_FILE_LINK_TYPE: Annotated[
        FileLinkType,
        Field(
            description=f"Default file link type to use with computational backend on-demand clusters '{list(FileLinkType)}'"
        ),
    ] = FileLinkType.PRESIGNED
    COMPUTATIONAL_BACKEND_MAX_WAITING_FOR_CLUSTER_TIMEOUT: Annotated[
        datetime.timedelta,
        Field(
            description="maximum time a pipeline can wait for a cluster to start"
            "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formatting)."
        ),
    ] = datetime.timedelta(minutes=10)

    COMPUTATIONAL_BACKEND_MAX_WAITING_FOR_RETRIEVING_RESULTS: Annotated[
        datetime.timedelta,
        Field(
            description="maximum time the computational scheduler waits until retrieving results from the computational backend is failed"
            "(default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formatting)."
        ),
    ] = datetime.timedelta(minutes=10)

    @cached_property
    def default_cluster(self) -> BaseCluster:
        return BaseCluster(
            name="Default cluster",
            endpoint=self.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL,
            authentication=self.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH,
            owner=1,  # NOTE: currently this is a soft hack (the group of everyone is the group 1)
            type=ClusterTypeInModel.ON_PREMISE,
        )

    @field_validator("COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH", mode="before")
    @classmethod
    def _empty_auth_is_none(cls, v):
        if not v:
            return NoAuthentication()
        return v


class AppSettings(BaseApplicationSettings, MixinLoggingSettings):
    LOG_LEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_V2_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
        ),
    ] = LogLevel.INFO

    DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED",
                "LOG_FORMAT_LOCAL_DEV_ENABLED",
            ),
            description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
        ),
    ] = False
    DIRECTOR_V2_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "DIRECTOR_V2_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY
    DIRECTOR_V2_DEV_FEATURES_ENABLED: bool = False

    DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED: Annotated[
        bool,
        Field(
            description=(
                "Under development feature. If enabled state "
                "is saved using rclone docker volumes."
            )
        ),
    ] = False

    # for passing self-signed certificate to spawned services
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_ID: Annotated[
        str,
        Field(
            description="ID of the docker secret containing the self-signed certificate"
        ),
    ] = ""
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME: Annotated[
        str,
        Field(
            description="Name of the docker secret containing the self-signed certificate"
        ),
    ] = ""
    DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME: Annotated[
        str,
        Field(
            description="Filepath to self-signed osparc.crt file *as mounted inside the container*, empty strings disables it"
        ),
    ] = ""
    DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    DIRECTOR_V2_PROFILING: bool = False

    DIRECTOR_V2_REMOTE_DEBUGGING_PORT: PortInt | None = None

    # extras
    SWARM_STACK_NAME: str = "undefined-please-check"
    SERVICE_TRACKING_HEARTBEAT: Annotated[
        datetime.timedelta,
        Field(
            description="Service scheduler heartbeat (everytime a heartbeat is sent into RabbitMQ)"
            " (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formatting)"
        ),
    ] = DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL

    SIMCORE_SERVICES_NETWORK_NAME: Annotated[
        str | None, Field(description="used to find the right network name")
    ] = None
    SIMCORE_SERVICES_PREFIX: Annotated[
        str | None,
        Field(
            description="useful when developing with an alternative registry namespace"
        ),
    ] = "simcore/services"

    DIRECTOR_V2_NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS: Annotated[
        NonNegativeInt, Field(description="forwarded to sidecars which use nodeports")
    ] = NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE

    # debug settings
    CLIENT_REQUEST: Annotated[
        ClientRequestSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ] = DEFAULT_FACTORY

    # App modules settings ---------------------
    DIRECTOR_V2_STORAGE: Annotated[
        StorageSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    DIRECTOR_V2_NODE_PORTS_STORAGE_AUTH: Annotated[
        StorageAuthSettings | None,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ] = None

    DIRECTOR_V2_CATALOG: Annotated[
        CatalogSettings | None, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    DIRECTOR_V0: Annotated[
        DirectorV0Settings, Field(json_schema_extra={"auto_default_from_env": True})
    ] = DEFAULT_FACTORY

    DYNAMIC_SERVICES: Annotated[
        DynamicServicesSettings,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ]

    POSTGRES: Annotated[
        PostgresSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    REDIS: Annotated[
        RedisSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ] = DEFAULT_FACTORY

    DIRECTOR_V2_RABBITMQ: Annotated[
        RabbitSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ] = DEFAULT_FACTORY

    TRAEFIK_SIMCORE_ZONE: str = "internal_simcore_stack"

    DIRECTOR_V2_COMPUTATIONAL_BACKEND: Annotated[
        ComputationalBackendSettings,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ] = DEFAULT_FACTORY

    DIRECTOR_V2_DOCKER_REGISTRY: Annotated[
        RegistrySettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for the private registry deployed with the platform",
        ),
    ] = DEFAULT_FACTORY
    DIRECTOR_V2_DOCKER_HUB_REGISTRY: Annotated[
        RegistrySettings | None, Field(description="public DockerHub registry settings")
    ] = None

    DIRECTOR_V2_RESOURCE_USAGE_TRACKER: Annotated[
        ResourceUsageTrackerSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="resource usage tracker service client's plugin",
        ),
    ] = DEFAULT_FACTORY

    DIRECTOR_V2_TRACING: Annotated[
        TracingSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="settings for opentelemetry tracing",
        ),
    ] = None

    @field_validator("LOG_LEVEL", mode="before")
    @classmethod
    def _validate_loglevel(cls, value: str) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level

    _validate_service_tracking_heartbeat = validate_numeric_string_as_timedelta(
        "SERVICE_TRACKING_HEARTBEAT"
    )


def get_application_settings(app: FastAPI) -> AppSettings:
    return cast(AppSettings, app.state.settings)
