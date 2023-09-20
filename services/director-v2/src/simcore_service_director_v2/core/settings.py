# pylint: disable=no-self-argument
# pylint: disable=no-self-use


import datetime
import logging
import random
import re
from enum import Enum, auto
from functools import cached_property
from pathlib import Path

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
    NoAuthentication,
)
from models_library.docker import DockerGenericTag
from models_library.projects_networks import DockerNetworkName
from models_library.utils.enums import StrAutoEnum
from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    ConstrainedStr,
    Field,
    PositiveFloat,
    PositiveInt,
    parse_obj_as,
    validator,
)
from settings_library.base import BaseCustomSettings
from settings_library.catalog import CatalogSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.http_client_request import ClientRequestSettings
from settings_library.postgres import PostgresSettings
from settings_library.r_clone import RCloneSettings as SettingsLibraryRCloneSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.resource_usage_tracker import (
    DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
    ResourceUsageTrackerSettings,
)
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_FASTAPI_PORT
from simcore_postgres_database.models.clusters import ClusterType
from simcore_sdk.node_ports_v2 import FileLinkType

from ..constants import DYNAMIC_SIDECAR_DOCKER_IMAGE_RE

logger = logging.getLogger(__name__)


MINS = 60
API_ROOT: str = "api"

SERVICE_RUNTIME_SETTINGS: str = "simcore.service.settings"
SERVICE_REVERSE_PROXY_SETTINGS: str = "simcore.service.reverse-proxy-settings"
SERVICE_RUNTIME_BOOTSETTINGS: str = "simcore.service.bootsettings"

SUPPORTED_TRAEFIK_LOG_LEVELS: set[str] = {"info", "debug", "warn", "error"}


class PlacementConstraintStr(ConstrainedStr):
    strip_whitespace = True
    regex = re.compile(
        r"^(?!-)(?![.])(?!.*--)(?!.*[.][.])[a-zA-Z0-9.-]*(?<!-)(?<![.])(!=|==)[a-zA-Z0-9_. -]*$"
    )


class VFSCacheMode(str, Enum):
    __slots__ = ()

    OFF = "off"
    MINIMAL = "minimal"
    WRITES = "writes"
    FULL = "full"


class EnvoyLogLevel(StrAutoEnum):
    TRACE = auto()
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()

    def to_log_level(self) -> str:
        lower_log_level: str = self.value.lower()
        return lower_log_level


class RCloneSettings(SettingsLibraryRCloneSettings):
    R_CLONE_DIR_CACHE_TIME_SECONDS: PositiveInt = Field(
        10,
        description="time to cache directory entries for",
    )
    R_CLONE_POLL_INTERVAL_SECONDS: PositiveInt = Field(
        9,
        description="time to wait between polling for changes",
    )
    R_CLONE_VFS_CACHE_MODE: VFSCacheMode = Field(
        VFSCacheMode.MINIMAL,
        description="used primarly for easy testing without requiring requiring code changes",
    )

    @validator("R_CLONE_POLL_INTERVAL_SECONDS")
    @classmethod
    def enforce_r_clone_requirement(cls, v: int, values) -> PositiveInt:
        dir_cache_time = values["R_CLONE_DIR_CACHE_TIME_SECONDS"]
        if not v < dir_cache_time:
            msg = f"R_CLONE_POLL_INTERVAL_SECONDS={v} must be lower than R_CLONE_DIR_CACHE_TIME_SECONDS={dir_cache_time}"
            raise ValueError(msg)
        return v


class StorageSettings(BaseCustomSettings):
    STORAGE_HOST: str = "storage"
    STORAGE_PORT: int = 8080
    STORAGE_VTAG: str = "v0"

    @cached_property
    def endpoint(self) -> str:
        url: str = AnyHttpUrl.build(
            scheme="http",
            host=self.STORAGE_HOST,
            path=f"/{self.STORAGE_VTAG}",
            port=f"{self.STORAGE_PORT}",
        )
        return url


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


class DynamicSidecarProxySettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_CADDY_VERSION: str = Field(
        "2.6.4-alpine",
        description="current version of the Caddy image to be pulled and used from dockerhub",
    )
    DYNAMIC_SIDECAR_CADDY_ADMIN_API_PORT: PortInt = Field(
        default_factory=lambda: random.randint(1025, 65535),  # noqa: S311
        description="port where to expose the proxy's admin API",
    )


class DynamicSidecarEgressSettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_ENVOY_IMAGE: DockerGenericTag = Field(
        "envoyproxy/envoy:v1.25-latest",
        description="envoy image to use",
    )
    DYNAMIC_SIDECAR_ENVOY_LOG_LEVEL: EnvoyLogLevel = Field(
        default=EnvoyLogLevel.ERROR,  # type: ignore
        description="log level for envoy proxy service",
    )


class DynamicSidecarSettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_SC_BOOT_MODE: BootModeEnum = Field(
        ...,
        description="Boot mode used for the dynamic-sidecar services"
        "By defaults, it uses the same boot mode set for the director-v2",
        env=["DYNAMIC_SIDECAR_SC_BOOT_MODE", "SC_BOOT_MODE"],
    )

    DYNAMIC_SIDECAR_LOG_LEVEL: str = Field(
        "WARNING",
        description="log level of the dynamic sidecar"
        "If defined, it captures global env vars LOG_LEVEL and LOGLEVEL from the director-v2 service",
        env=["DYNAMIC_SIDECAR_LOG_LEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    DYNAMIC_SIDECAR_IMAGE: str = Field(
        ...,
        regex=DYNAMIC_SIDECAR_DOCKER_IMAGE_RE,
        description="used by the director to start a specific version of the dynamic-sidecar",
    )

    SIMCORE_SERVICES_NETWORK_NAME: DockerNetworkName = Field(
        ...,
        description="network all dynamic services are connected to",
    )

    DYNAMIC_SIDECAR_DOCKER_COMPOSE_VERSION: str = Field(
        "3.8", description="docker-compose spec version used in the compose-specs"
    )

    DYNAMIC_SIDECAR_ENABLE_VOLUME_LIMITS: bool = Field(
        default=False,
        description="enables support for limiting service's volume size",
    )

    SWARM_STACK_NAME: str = Field(
        ...,
        description="in case there are several deployments on the same docker swarm, it is attached as a label on all spawned services",
    )

    TRAEFIK_SIMCORE_ZONE: str = Field(
        ...,
        description="Names the traefik zone for services that must be accessible from platform http entrypoint",
    )

    DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS: dict[str, str] = Field(
        ...,
        description=(
            "Provided by ops, are injected as service labels when starting the dy-sidecar, "
            "and Prometheus identifies the service as to be scraped"
        ),
    )

    DYNAMIC_SIDECAR_PROXY_SETTINGS: DynamicSidecarProxySettings = Field(
        auto_default_from_env=True
    )

    DYNAMIC_SIDECAR_EGRESS_PROXY_SETTINGS: DynamicSidecarEgressSettings = Field(
        auto_default_from_env=True
    )

    DYNAMIC_SIDECAR_R_CLONE_SETTINGS: RCloneSettings = Field(auto_default_from_env=True)

    #
    # TIMEOUTS AND RETRY dark worlds
    #

    DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT: PositiveFloat = Field(
        15.0,
        description=(
            "the default timeout each request to the dynamic-sidecar API in seconds; as per "
            "design, all requests should answer quite quickly, in theory a few seconds or less"
        ),
    )
    DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT: PositiveFloat = Field(
        5.0,
        description=(
            "Connections to the dynamic-sidecars in the same swarm deployment should be very fast."
        ),
    )
    DYNAMIC_SIDECAR_STARTUP_TIMEOUT_S: PositiveFloat = Field(
        60 * MINS,
        description=(
            "After starting the dynamic-sidecar its docker_node_id is required. "
            "This operation can be slow based on system load, sometimes docker "
            "swarm takes more than seconds to assign the node."
            "Autoscaling of nodes takes time, it is required to wait longer"
            "for nodes to be assigned."
        ),
    )
    DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT: PositiveFloat = Field(
        60.0 * MINS,
        description=(
            "When saving and restoring the state of a dynamic service, depending on the payload "
            "some services take longer or shorter to save and restore. Across the "
            "platform this value is set to 1 hour."
        ),
    )
    DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT: PositiveFloat = Field(
        1.0 * MINS,
        description=(
            "Restarts all started containers. During this operation, no data "
            "stored in the container will be lost as docker compose restart "
            "will not alter the state of the files on the disk nor its environment."
        ),
    )
    DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START: PositiveFloat = Field(
        60.0 * MINS,
        description=(
            "When starting container (`docker compose up`), images might "
            "require pulling before containers are started."
        ),
    )
    DYNAMIC_SIDECAR_WAIT_FOR_SERVICE_TO_STOP: PositiveFloat = Field(
        60.0 * MINS,
        description=(
            "When stopping a service, depending on the amount of data to store, "
            "the operation might be very long. Also all relative created resources: "
            "services, containsers, volumes and networks need to be removed. "
        ),
    )

    DYNAMIC_SIDECAR_PROJECT_NETWORKS_ATTACH_DETACH_S: PositiveFloat = Field(
        3.0 * MINS,
        description=(
            "timeout for attaching/detaching project networks to/from a container"
        ),
    )
    DYNAMIC_SIDECAR_VOLUMES_REMOVAL_TIMEOUT_S: PositiveFloat = Field(
        1.0 * MINS,
        description=(
            "time to wait before giving up on removing dynamic-sidecar's volumes"
        ),
    )
    DYNAMIC_SIDECAR_STATUS_API_TIMEOUT_S: PositiveFloat = Field(
        1.0,
        description=(
            "when requesting the status of a service this is the "
            "maximum amount of time the request can last"
        ),
    )

    DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S: PositiveFloat = Field(
        1 * MINS,
        description=(
            "Connectivity between director-v2 and a dy-sidecar can be "
            "temporarily disrupted if network between swarm nodes has "
            "issues. To avoid the sidecar being marked as failed, "
            "allow for some time to pass before declaring it failed."
        ),
    )

    #
    # DEVELOPMENT ONLY config
    #

    DYNAMIC_SIDECAR_MOUNT_PATH_DEV: Path | None = Field(
        None,
        description="Host path to the dynamic-sidecar project. Used as source path to mount to the dynamic-sidecar [DEVELOPMENT ONLY]",
        example="osparc-simcore/services/dynamic-sidecar",
    )

    DYNAMIC_SIDECAR_PORT: PortInt = Field(
        DEFAULT_FASTAPI_PORT,
        description="port on which the webserver for the dynamic-sidecar is exposed [DEVELOPMENT ONLY]",
    )

    DYNAMIC_SIDECAR_EXPOSE_PORT: bool = Field(
        default=False,
        description="Publishes the service on localhost for debuging and testing [DEVELOPMENT ONLY]"
        "Can be used to access swagger doc from the host as http://127.0.0.1:30023/dev/doc "
        "where 30023 is the host published port",
    )

    PROXY_EXPOSE_PORT: bool = Field(
        default=False,
        description="exposes the proxy on localhost for debuging and testing",
    )

    DYNAMIC_SIDECAR_DOCKER_NODE_RESOURCE_LIMITS_ENABLED: bool = Field(
        default=False,
        description=(
            "Limits concurrent service saves for a docker node. Guarantees "
            "that no more than X services use a resource together. "
            "NOTE: A node can end up with all the services from a single study. "
            "When the study is closed/opened all the services will try to "
            "upload/download their data. This causes a lot of disk "
            "and network stress (especially for low power nodes like in AWS). "
            "Some nodes collapse under load or behave unexpectedly."
        ),
    )
    DYNAMIC_SIDECAR_DOCKER_NODE_CONCURRENT_RESOURCE_SLOTS: PositiveInt = Field(
        2, description="Amount of slots per resource on a node"
    )
    DYNAMIC_SIDECAR_DOCKER_NODE_SAVES_LOCK_TIMEOUT_S: PositiveFloat = Field(
        10,
        description=(
            "Lifetime of the lock. Allows the system to recover a lock "
            "in case of crash, the lock will expire and result as released."
        ),
    )

    @validator("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", pre=True)
    @classmethod
    def auto_disable_if_production(cls, v, values):
        if v and values.get("DYNAMIC_SIDECAR_SC_BOOT_MODE") == BootModeEnum.PRODUCTION:
            logger.warning(
                "In production DYNAMIC_SIDECAR_MOUNT_PATH_DEV cannot be set to %s, enforcing None",
                v,
            )
            return None
        return v

    @validator("DYNAMIC_SIDECAR_EXPOSE_PORT", pre=True, always=True)
    @classmethod
    def auto_enable_if_development(cls, v, values):
        if (
            boot_mode := values.get("DYNAMIC_SIDECAR_SC_BOOT_MODE")
        ) and boot_mode.is_devel_mode():
            # Can be used to access swagger doc from the host as http://127.0.0.1:30023/dev/doc
            return True
        return v

    @validator("DYNAMIC_SIDECAR_IMAGE", pre=True)
    @classmethod
    def strip_leading_slashes(cls, v: str) -> str:
        return v.lstrip("/")

    @validator("DYNAMIC_SIDECAR_LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        if v not in valid_log_levels:
            msg = f"Log level must be one of {valid_log_levels} not {v}"
            raise ValueError(msg)
        return v


class DynamicServicesSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED: bool = True

    DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS: PositiveFloat = Field(
        5.0, description="interval at which the scheduler cycle is repeated"
    )

    DIRECTOR_V2_DYNAMIC_SCHEDULER_PENDING_VOLUME_REMOVAL_INTERVAL_S: PositiveFloat = (
        Field(
            30 * MINS,
            description="interval at which cleaning of unused dy-sidecar "
            "docker volume removal services is executed",
        )
    )


class DynamicServicesSettings(BaseCustomSettings):
    # TODO: PC->ANE: refactor dynamic-sidecar settings. One settings per app module
    # WARNING: THIS IS NOT the same module as dynamic-sidecar
    DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED: bool = Field(
        default=True, description="Enables/Disables the dynamic_sidecar submodule"
    )

    DYNAMIC_SIDECAR: DynamicSidecarSettings = Field(auto_default_from_env=True)

    DYNAMIC_SCHEDULER: DynamicServicesSchedulerSettings = Field(
        auto_default_from_env=True
    )


class ComputationalBackendSettings(BaseCustomSettings):
    COMPUTATIONAL_BACKEND_ENABLED: bool = Field(
        default=True,
    )
    COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED: bool = Field(
        default=True,
    )
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL: AnyUrl = Field(
        parse_obj_as(AnyUrl, "tcp://dask-scheduler:8786"),
        description="This is the cluster that will be used by default"
        " when submitting computational services (typically "
        "tcp://dask-scheduler:8786 for the internal cluster, or "
        "http(s)/GATEWAY_IP:8000 for a osparc-dask-gateway)",
    )
    COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH: ClusterAuthentication | None = Field(
        NoAuthentication(),
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
            type=ClusterType.ON_PREMISE,
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
        "",
        description="ID of the docker secret containing the self-signed certificate",
    )
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME: str = Field(
        "",
        description="Name of the docker secret containing the self-signed certificate",
    )
    DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME: str = Field(
        "",
        description="Filepath to self-signed osparc.crt file *as mounted inside the container*, empty strings disables it",
    )

    # extras
    EXTRA_HOSTS_SUFFIX: str = Field("undefined", env="EXTRA_HOSTS_SUFFIX")
    PUBLISHED_HOSTS_NAME: str = Field("", env="PUBLISHED_HOSTS_NAME")
    SWARM_STACK_NAME: str = Field("undefined-please-check", env="SWARM_STACK_NAME")
    SERVICE_TRACKING_HEARTBEAT: datetime.timedelta = Field(
        default=DEFAULT_RESOURCE_USAGE_HEARTBEAT_INTERVAL,
        description="Service scheduler heartbeat (everytime a heartbeat is sent into RabbitMQ)",
    )

    SIMCORE_SERVICES_NETWORK_NAME: str | None = Field(
        default=None,
        description="used to find the right network name",
    )
    SIMCORE_SERVICES_PREFIX: str | None = Field(
        "simcore/services",
        description="useful when developing with an alternative registry namespace",
    )

    # monitoring
    MONITORING_ENABLED: bool = False

    # fastappi app settings
    DIRECTOR_V2_DEBUG: bool = False

    # ptvsd settings
    DIRECTOR_V2_REMOTE_DEBUG_PORT: PortInt = PortInt(3000)

    CLIENT_REQUEST: ClientRequestSettings = Field(auto_default_from_env=True)

    # App modules settings ---------------------
    DIRECTOR_V2_STORAGE: StorageSettings = Field(auto_default_from_env=True)

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

    DIRECTOR_V2_DOCKER_REGISTRY: RegistrySettings = Field(auto_default_from_env=True)

    DIRECTOR_V2_RESOURCE_USAGE_TRACKER: ResourceUsageTrackerSettings = Field(
        auto_default_from_env=True,
        description="resource usage tracker service client's plugin",
    )

    # This is just a service placement constraint, see
    # https://docs.docker.com/engine/swarm/services/#control-service-placement.
    DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS: list[PlacementConstraintStr] = Field(
        default_factory=list,
        example='["node.labels.region==east", "one!=yes"]',
    )

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value: str) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level
