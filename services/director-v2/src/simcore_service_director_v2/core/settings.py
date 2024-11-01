# pylint: disable=no-self-argument
# pylint: disable=no-self-use


import datetime
from functools import cached_property

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from models_library.clusters import (
    DEFAULT_CLUSTER_ID,
    Cluster,
    ClusterAuthentication,
    ClusterTypeInModel,
    NoAuthentication,
)
from pydantic import AnyHttpUrl, AnyUrl, Field, NonNegativeInt, validator
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.base import BaseCustomSettings
from settings_library.catalog import CatalogSettings
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


class DirectorV0Settings(BaseCustomSettings):
    DIRECTOR_V0_ENABLED: bool = True

    DIRECTOR_HOST: str = "director"
    DIRECTOR_PORT: PortInt = PortInt(8080)
    DIRECTOR_V0_VTAG: VersionTag = Field(
        default="v0", description="Director-v0 service API's version tag"
    )

    @cached_property
    def endpoint(self) -> str:
        url: str = AnyHttpUrl.build(
            scheme="http",
            host=self.DIRECTOR_HOST,
            port=f"{self.DIRECTOR_PORT}",
            path=f"/{self.DIRECTOR_V0_VTAG}",
        )
        return url


class ComputationalBackendSettings(BaseCustomSettings):
    COMPUTATIONAL_BACKEND_ENABLED: bool = Field(
        default=True,
    )
    COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED: bool = Field(
        default=True,
    )
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL: AnyUrl = Field(
        ...,
        description="This is the cluster that will be used by default"
        " when submitting computational services (typically "
        "tcp://dask-scheduler:8786, tls://dask-scheduler:8786 for the internal cluster, or "
        "http(s)/GATEWAY_IP:8000 for a osparc-dask-gateway)",
    )
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH: ClusterAuthentication = Field(
        ...,
        description="Empty for the internal cluster, must be one "
        "of simple/kerberos/jupyterhub for the osparc-dask-gateway",
    )
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_FILE_LINK_TYPE: FileLinkType = Field(
        FileLinkType.S3,
        description=f"Default file link type to use with the internal cluster '{list(FileLinkType)}'",
    )
    COMPUTATIONAL_BACKEND_DEFAULT_FILE_LINK_TYPE: FileLinkType = Field(
        FileLinkType.PRESIGNED,
        description=f"Default file link type to use with computational backend '{list(FileLinkType)}'",
    )
    COMPUTATIONAL_BACKEND_ON_DEMAND_CLUSTERS_FILE_LINK_TYPE: FileLinkType = Field(
        FileLinkType.PRESIGNED,
        description=f"Default file link type to use with computational backend on-demand clusters '{list(FileLinkType)}'",
    )

    @cached_property
    def default_cluster(self) -> Cluster:
        return Cluster(
            id=DEFAULT_CLUSTER_ID,
            name="Default cluster",
            endpoint=self.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL,
            authentication=self.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH,
            owner=1,  # NOTE: currently this is a soft hack (the group of everyone is the group 1)
            type=ClusterTypeInModel.ON_PREMISE,
        )

    @validator("COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH", pre=True)
    @classmethod
    def _empty_auth_is_none(cls, v):
        if not v:
            return NoAuthentication()
        return v


class AppSettings(BaseCustomSettings, MixinLoggingSettings):
    # docker environs
    SC_BOOT_MODE: BootModeEnum
    SC_BOOT_TARGET: BuildTargetEnum | None

    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["DIRECTOR_V2_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=[
            "DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED",
            "LOG_FORMAT_LOCAL_DEV_ENABLED",
        ],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    DIRECTOR_V2_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        env=["DIRECTOR_V2_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )
    DIRECTOR_V2_DEV_FEATURES_ENABLED: bool = False

    DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED: bool = Field(
        default=False,
        description=(
            "Under development feature. If enabled state "
            "is saved using rclone docker volumes."
        ),
    )

    # for passing self-signed certificate to spawned services
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_ID: str = Field(
        default="",
        description="ID of the docker secret containing the self-signed certificate",
    )
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME: str = Field(
        default="",
        description="Name of the docker secret containing the self-signed certificate",
    )
    DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME: str = Field(
        default="",
        description="Filepath to self-signed osparc.crt file *as mounted inside the container*, empty strings disables it",
    )
    DIRECTOR_V2_PROMETHEUS_INSTRUMENTATION_ENABLED: bool = True
    DIRECTOR_V2_PROFILING: bool = False

    DIRECTOR_V2_REMOTE_DEBUGGING_PORT: PortInt | None

    # extras
    SWARM_STACK_NAME: str = Field("undefined-please-check", env="SWARM_STACK_NAME")
    SERVICE_TRACKING_HEARTBEAT: datetime.timedelta = Field(
        default=DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
        description="Service scheduler heartbeat (everytime a heartbeat is sent into RabbitMQ)"
        " (default to seconds, or see https://pydantic-docs.helpmanual.io/usage/types/#datetime-types for string formating)",
    )

    SIMCORE_SERVICES_NETWORK_NAME: str | None = Field(
        default=None,
        description="used to find the right network name",
    )
    SIMCORE_SERVICES_PREFIX: str | None = Field(
        "simcore/services",
        description="useful when developing with an alternative registry namespace",
    )

    DIRECTOR_V2_NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS: NonNegativeInt = Field(
        default=NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE,
        description="forwarded to sidecars which use nodeports",
    )

    # debug settings
    CLIENT_REQUEST: ClientRequestSettings = Field(auto_default_from_env=True)

    # App modules settings ---------------------
    DIRECTOR_V2_STORAGE: StorageSettings = Field(auto_default_from_env=True)
    DIRECTOR_V2_NODE_PORTS_STORAGE_AUTH: StorageAuthSettings | None = Field(
        auto_default_from_env=True
    )

    DIRECTOR_V2_CATALOG: CatalogSettings | None = Field(auto_default_from_env=True)

    DIRECTOR_V0: DirectorV0Settings = Field(auto_default_from_env=True)

    DYNAMIC_SERVICES: DynamicServicesSettings = Field(auto_default_from_env=True)

    POSTGRES: PostgresSettings = Field(auto_default_from_env=True)

    REDIS: RedisSettings = Field(auto_default_from_env=True)

    DIRECTOR_V2_RABBITMQ: RabbitSettings = Field(auto_default_from_env=True)

    TRAEFIK_SIMCORE_ZONE: str = Field("internal_simcore_stack")

    DIRECTOR_V2_COMPUTATIONAL_BACKEND: ComputationalBackendSettings = Field(
        auto_default_from_env=True
    )

    DIRECTOR_V2_DOCKER_REGISTRY: RegistrySettings = Field(
        auto_default_from_env=True,
        description="settings for the private registry deployed with the platform",
    )
    DIRECTOR_V2_DOCKER_HUB_REGISTRY: RegistrySettings | None = Field(
        description="public DockerHub registry settings"
    )

    DIRECTOR_V2_RESOURCE_USAGE_TRACKER: ResourceUsageTrackerSettings = Field(
        auto_default_from_env=True,
        description="resource usage tracker service client's plugin",
    )

    DIRECTOR_V2_PUBLIC_API_BASE_URL: AnyHttpUrl = Field(
        ...,
        description="Base URL used to access the public api e.g. http://127.0.0.1:6000 for development or https://api.osparc.io",
    )
    DIRECTOR_V2_TRACING: TracingSettings | None = Field(
        auto_default_from_env=True, description="settings for opentelemetry tracing"
    )

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value: str) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level
