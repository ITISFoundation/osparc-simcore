# pylint: disable=no-self-argument
# pylint: disable=no-self-use

from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import Dict, Optional, Set

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from models_library.services import SERVICE_NETWORK_RE
from pydantic import AnyHttpUrl, Field, PositiveFloat, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.docker_registry import RegistrySettings
from settings_library.http_client_request import ClientRequestSettings
from settings_library.postgres import PostgresSettings
from settings_library.rabbit import RabbitSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings

from ..meta import API_VTAG
from ..models.schemas.constants import DYNAMIC_SIDECAR_DOCKER_IMAGE_RE, ClusterID

MINS = 60
API_ROOT: str = "api"

SERVICE_RUNTIME_SETTINGS: str = "simcore.service.settings"
SERVICE_REVERSE_PROXY_SETTINGS: str = "simcore.service.reverse-proxy-settings"
SERVICE_RUNTIME_BOOTSETTINGS: str = "simcore.service.bootsettings"

ORG_LABELS_TO_SCHEMA_LABELS: Dict[str, str] = {
    "org.label-schema.build-date": "build_date",
    "org.label-schema.vcs-ref": "vcs_ref",
    "org.label-schema.vcs-url": "vcs_url",
}

SUPPORTED_TRAEFIK_LOG_LEVELS: Set[str] = {"info", "debug", "warn", "error"}


class S3Provider(str, Enum):
    AWS = "AWS"
    CEPH = "CEPH"
    MINIO = "MINIO"


class VFSCacheMode(str, Enum):
    OFF = "off"
    MINIMAL = "minimal"
    WRITES = "writes"
    FILL = "full"


class RCloneSettings(S3Settings):
    R_CLONE_S3_PROVIDER: S3Provider

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
    def enforce_r_clone_requirement(cls, v, values) -> PositiveInt:
        dir_cache_time = values["R_CLONE_DIR_CACHE_TIME_SECONDS"]
        if not v < dir_cache_time:
            raise ValueError(
                (
                    f"R_CLONE_POLL_INTERVAL_SECONDS={v} must be lower "
                    f"than R_CLONE_DIR_CACHE_TIME_SECONDS={dir_cache_time}"
                )
            )
        return v

    @cached_property
    def endpoint(self) -> str:
        if not self.S3_ENDPOINT.startswith("http"):
            scheme = "https" if self.S3_SECURE else "http"
            return f"{scheme}://{self.S3_ENDPOINT}"
        return self.S3_ENDPOINT


class DirectorV0Settings(BaseCustomSettings):
    DIRECTOR_V0_ENABLED: bool = True

    DIRECTOR_HOST: str = "director"
    DIRECTOR_PORT: PortInt = 8080
    DIRECTOR_V0_VTAG: VersionTag = Field(
        "v0", description="Director-v0 service API's version tag"
    )

    @cached_property
    def endpoint(self) -> str:
        return AnyHttpUrl.build(
            scheme="http",
            host=self.DIRECTOR_HOST,
            port=f"{self.DIRECTOR_PORT}",
            path=f"/{self.DIRECTOR_V0_VTAG}",
        )


class DynamicSidecarProxySettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_CADDY_VERSION: str = Field(
        "2.4.5-alpine",
        description="current version of the Caddy image to be pulled and used from dockerhub",
    )


class DynamicSidecarSettings(BaseCustomSettings):
    SC_BOOT_MODE: BootModeEnum = Field(
        BootModeEnum.PRODUCTION,
        description="Used to compute where or not should start sidecar in development mode",
    )
    DYNAMIC_SIDECAR_IMAGE: str = Field(
        ...,
        regex=DYNAMIC_SIDECAR_DOCKER_IMAGE_RE,
        description="used by the director to start a specific version of the dynamic-sidecar",
    )

    DYNAMIC_SIDECAR_PORT: PortInt = Field(
        8000,
        description="port on which the webserver for the dynamic-sidecar is exposed",
    )
    DYNAMIC_SIDECAR_MOUNT_PATH_DEV: Optional[Path] = Field(
        None,
        description="optional, only used for development, mounts the source of the dynamic-sidecar",
    )

    DYNAMIC_SIDECAR_EXPOSE_PORT: bool = Field(
        False,
        description="exposes the service on localhost for debuging and testing",
    )
    PROXY_EXPOSE_PORT: bool = Field(
        False,
        description="exposes the proxy on localhost for debuging and testing",
    )

    SIMCORE_SERVICES_NETWORK_NAME: str = Field(
        ...,
        regex=SERVICE_NETWORK_RE,
        description="network all dynamic services are connected to",
    )
    DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT: PositiveFloat = Field(
        15.0,
        description=(
            "the default timeout each request to the dynamic-sidecar API in seconds; as per "
            "design, all requests should answer quite quickly, in theory a few seconds or less"
        ),
    )
    DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT: PositiveFloat = Field(
        1.0,
        description=(
            "Connections to the dynamic-sidecars in the same swarm deployment should be very fast."
        ),
    )
    DYNAMIC_SIDECAR_TIMEOUT_FETCH_DYNAMIC_SIDECAR_NODE_ID: PositiveFloat = Field(
        60.0,
        description=(
            "When starting the dynamic-sidecar proxy, the NodeID of the dynamic-sidecar container "
            "is required. If something goes wrong timeout and do not wait forever in a loop. "
            "This is used to scheduler the status of the service via aiodocker and not http requests "
            "twards the dynamic-sidecar, as is the case with the above timeout field."
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
            "stored in the container will be lost as docker-compose restart "
            "will not alter the state of the files on the disk nor its environment."
        ),
    )
    DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START: PositiveFloat = Field(
        60.0 * MINS,
        description=(
            "After running `docker-compose up`, images might need to be pulled "
            "before everything is started. Using default 1hour timeout to let this "
            "operation finish."
        ),
    )

    TRAEFIK_SIMCORE_ZONE: str = Field(
        ...,
        description="Names the traefik zone for services that must be accessible from platform http entrypoint",
    )

    DYNAMIC_SIDECAR_R_CLONE_SETTINGS: RCloneSettings = Field(auto_default_from_env=True)

    SWARM_STACK_NAME: str = Field(
        ...,
        description="in case there are several deployments on the same docker swarm, it is attached as a label on all spawned services",
    )

    DYNAMIC_SIDECAR_PROXY_SETTINGS: DynamicSidecarProxySettings = Field(
        auto_default_from_env=True
    )

    DYNAMIC_SIDECAR_DOCKER_COMPOSE_VERSION: str = Field(
        "3.8", description="docker-compose version used in the compose-specs"
    )

    @validator("DYNAMIC_SIDECAR_IMAGE", pre=True)
    @classmethod
    def strip_leading_slashes(cls, v) -> str:
        return v.lstrip("/")


class DynamicServicesSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SCHEDULER_ENABLED: bool = True

    DIRECTOR_V2_DYNAMIC_SCHEDULER_INTERVAL_SECONDS: PositiveFloat = Field(
        5.0, description="interval at which the scheduler cycle is repeated"
    )

    DIRECTOR_V2_DYNAMIC_SCHEDULER_MAX_STATUS_API_DURATION: PositiveFloat = Field(
        1.0,
        description=(
            "when requesting the status of a service this is the "
            "maximum amount of time the request can last"
        ),
    )


class DynamicServicesSettings(BaseCustomSettings):
    # TODO: PC->ANE: refactor dynamic-sidecar settings. One settings per app module
    # WARNING: THIS IS NOT the same module as dynamic-sidecar
    DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED: bool = Field(
        True, description="Enables/Disables the dynamic_sidecar submodule"
    )

    DYNAMIC_SIDECAR: DynamicSidecarSettings = Field(auto_default_from_env=True)

    DYNAMIC_SCHEDULER: DynamicServicesSchedulerSettings = Field(
        auto_default_from_env=True
    )


class PGSettings(PostgresSettings):
    DIRECTOR_V2_POSTGRES_ENABLED: bool = Field(
        True,
        description="Enables/Disables connection with service",
    )


class DaskSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DASK_SCHEDULER_ENABLED: bool = Field(
        True,
    )
    DIRECTOR_V2_DASK_CLIENT_ENABLED: bool = Field(
        True,
    )
    DASK_SCHEDULER_HOST: str = Field(
        "dask-scheduler",
        description="Address of the scheduler to register (only if started as worker )",
    )
    DASK_SCHEDULER_PORT: PortInt = 8786

    DASK_DEFAULT_CLUSTER_ID: Optional[ClusterID] = Field(
        0, description="This defines the default cluster id when none is defined"
    )


class AppSettings(BaseCustomSettings, MixinLoggingSettings):

    # docker environs
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_BOOT_TARGET: Optional[BuildTargetEnum]

    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["DIRECTOR_V2_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    DIRECTOR_V2_DEV_FEATURES_ENABLED: bool = False

    # for passing self-signed certificate to spawned services
    # TODO: fix these variables once the timeout-minutes: 30 is able to start dynamic services
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_ID: str = ""
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME: str = ""
    DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME: str = ""

    # extras
    EXTRA_HOSTS_SUFFIX: str = Field("undefined", env="EXTRA_HOSTS_SUFFIX")
    PUBLISHED_HOSTS_NAME: str = Field("", env="PUBLISHED_HOSTS_NAME")
    SWARM_STACK_NAME: str = Field("undefined-please-check", env="SWARM_STACK_NAME")

    NODE_SCHEMA_LOCATION: str = Field(
        f"{API_ROOT}/{API_VTAG}/schemas/node-meta-v0.0.1.json",
        description="used when in devel mode vs release mode",
    )

    SIMCORE_SERVICES_NETWORK_NAME: Optional[str] = Field(
        None,
        description="used to find the right network name",
    )
    SIMCORE_SERVICES_PREFIX: Optional[str] = Field(
        "simcore/services",
        description="useful when developing with an alternative registry namespace",
    )

    # monitoring
    MONITORING_ENABLED: bool = False

    # fastappi app settings
    DIRECTOR_V2_DEBUG: bool = False

    # ptvsd settings
    DIRECTOR_V2_REMOTE_DEBUG_PORT: PortInt = 3000

    CLIENT_REQUEST: ClientRequestSettings = Field(auto_default_from_env=True)

    # App modules settings ---------------------

    DIRECTOR_V0: DirectorV0Settings = Field(auto_default_from_env=True)

    DYNAMIC_SERVICES: DynamicServicesSettings = Field(auto_default_from_env=True)

    POSTGRES: PGSettings = Field(auto_default_from_env=True)

    DIRECTOR_V2_RABBITMQ: RabbitSettings = Field(auto_default_from_env=True)

    STORAGE_ENDPOINT: str = Field("storage:8080", env="STORAGE_ENDPOINT")

    TRAEFIK_SIMCORE_ZONE: str = Field("internal_simcore_stack")

    DASK_SCHEDULER: DaskSchedulerSettings = Field(auto_default_from_env=True)

    DIRECTOR_V2_TRACING: Optional[TracingSettings] = Field(auto_default_from_env=True)

    DIRECTOR_V2_DOCKER_REGISTRY: RegistrySettings = Field(auto_default_from_env=True)

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        return cls.validate_log_level(value)
