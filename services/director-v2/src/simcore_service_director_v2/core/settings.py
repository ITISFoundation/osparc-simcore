from functools import cached_property

# pylint: disable=no-self-argument
# pylint: disable=no-self-use
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
from pydantic import AnyHttpUrl, Field, PositiveFloat, validator
from settings_library.base import BaseCustomSettings
from settings_library.celery import CelerySettings as BaseCelerySettings
from settings_library.docker_registry import RegistrySettings
from settings_library.logging_utils import MixinLoggingSettings
from settings_library.postgres import PostgresSettings

from ..meta import api_vtag
from ..models.schemas.constants import DYNAMIC_SIDECAR_DOCKER_IMAGE_RE

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


class ClientRequestSettings(BaseCustomSettings):
    # NOTE: when updating the defaults please make sure to search for the env vars
    # in all the project, they also need to be updated inside the service-library
    HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT: Optional[int] = Field(
        default=20,
        description="timeout used for outgoing http requests",
    )

    HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT: Optional[int] = Field(
        default=None,
        description=(
            "Maximal number of seconds for acquiring a connection"
            " from pool. The time consists connection establishment"
            " for a new connection or waiting for a free connection"
            " from a pool if pool connection limits are exceeded. "
            "For pure socket connection establishment time use sock_connect."
        ),
    )

    HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT: Optional[int] = Field(
        default=5,
        description=(
            "aiohttp specific field used in ClientTimeout, timeout for connecting to a "
            "peer for a new connection not given a pool"
        ),
    )


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


class CelerySettings(BaseCelerySettings):
    DIRECTOR_V2_CELERY_ENABLED: bool = Field(
        True, description="Enables/Disables connection with service"
    )
    CELERY_PUBLICATION_TIMEOUT: int = 60


class DynamicSidecarTraefikSettings(BaseCustomSettings):
    DYNAMIC_SIDECAR_TRAEFIK_VERSION: str = Field(
        "v2.4.13",
        description="current version of the Traefik image to be pulled and used from dockerhub",
    )
    DYNAMIC_SIDECAR_TRAEFIK_LOGLEVEL: str = Field(
        "warn", description="set Treafik's loglevel to be used"
    )

    DYNAMIC_SIDECAR_TRAEFIK_ACCESS_LOG: bool = Field(
        False, description="enables or disables access log"
    )

    @validator("DYNAMIC_SIDECAR_TRAEFIK_LOGLEVEL", pre=True)
    @classmethod
    def validate_log_level(cls, v) -> str:
        if v not in SUPPORTED_TRAEFIK_LOG_LEVELS:
            message = (
                "Got log level '{v}', expected one of '{SUPPORTED_TRAEFIK_LOG_LEVELS}'"
            )
            raise ValueError(message)
        return v

    @cached_property
    def access_log_as_string(self) -> str:
        return str(self.DYNAMIC_SIDECAR_TRAEFIK_ACCESS_LOG).lower()


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

    TRAEFIK_SIMCORE_ZONE: str = Field(
        ...,
        description="Names the traefik zone for services that must be accessible from platform http entrypoint",
    )

    SWARM_STACK_NAME: str = Field(
        ...,
        description="in case there are several deployments on the same docker swarm, it is attached as a label on all spawned services",
    )

    DYNAMIC_SIDECAR_TRAEFIK_SETTINGS: DynamicSidecarTraefikSettings

    REGISTRY: RegistrySettings

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

    DYNAMIC_SIDECAR: DynamicSidecarSettings

    DYNAMIC_SCHEDULER: DynamicServicesSchedulerSettings


class PGSettings(PostgresSettings):
    DIRECTOR_V2_POSTGRES_ENABLED: bool = Field(
        True,
        description="Enables/Disables connection with service",
    )


class CelerySchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_CELERY_SCHEDULER_ENABLED: bool = Field(
        True,
        description="Enables/Disables the scheduler",
    )


class DaskSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DASK_SCHEDULER_ENABLED: bool = Field(
        False,
    )
    DIRECTOR_V2_DASK_CLIENT_ENABLED: bool = Field(
        False,
    )
    DASK_SCHEDULER_HOST: str = Field(
        "dask-scheduler",
        description="Address of the scheduler to register (only if started as worker )",
    )
    DASK_SCHEDULER_PORT: PortInt = 8786

    DASK_CLUSTER_ID_PREFIX: Optional[str] = Field(
        "CLUSTER_", description="This defines the cluster name prefix"
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
        f"{API_ROOT}/{api_vtag}/schemas/node-meta-v0.0.1.json",
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

    CLIENT_REQUEST: ClientRequestSettings

    # App modules settings ---------------------

    CELERY: CelerySettings

    DIRECTOR_V0: DirectorV0Settings

    DYNAMIC_SERVICES: DynamicServicesSettings

    POSTGRES: PGSettings

    STORAGE_ENDPOINT: str = Field("storage:8080", env="STORAGE_ENDPOINT")

    TRAEFIK_SIMCORE_ZONE: str = Field("internal_simcore_stack")

    CELERY_SCHEDULER: CelerySchedulerSettings

    DASK_SCHEDULER: DaskSchedulerSettings

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        return cls.validate_log_level(value)

    @validator("DASK_SCHEDULER")
    @classmethod
    def _check_only_one_comp_scheduler_enabled(cls, v, values) -> DaskSchedulerSettings:
        celery_settings: CelerySchedulerSettings = values["CELERY_SCHEDULER"]
        dask_settings: DaskSchedulerSettings = v
        if (
            celery_settings.DIRECTOR_V2_CELERY_SCHEDULER_ENABLED
            and dask_settings.DIRECTOR_V2_DASK_SCHEDULER_ENABLED
        ):
            celery_settings.DIRECTOR_V2_CELERY_SCHEDULER_ENABLED = False
        return v
