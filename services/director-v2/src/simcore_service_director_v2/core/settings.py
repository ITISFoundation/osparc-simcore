from functools import cached_property

# pylint: disable=no-self-argument
# pylint: disable=no-self-use
from typing import Optional

from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from pydantic import AnyHttpUrl, Field, validator
from settings_library.base import BaseCustomSettings
from settings_library.celery import CelerySettings as BaseCelerySettings
from settings_library.logging_utils import MixinLoggingSettings
from settings_library.postgres import PostgresSettings

from ..meta import api_vtag

MINS = 60
API_ROOT: str = "api"

SERVICE_RUNTIME_SETTINGS: str = "simcore.service.settings"
SERVICE_REVERSE_PROXY_SETTINGS: str = "simcore.service.reverse-proxy-settings"
SERVICE_RUNTIME_BOOTSETTINGS: str = "simcore.service.bootsettings"

ORG_LABELS_TO_SCHEMA_LABELS = {
    "org.label-schema.build-date": "build_date",
    "org.label-schema.vcs-ref": "vcs_ref",
    "org.label-schema.vcs-url": "vcs_url",
}


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

    DIRECTOR_V0_HOST: str = "director"
    DIRECTOR_V0_PORT: PortInt = 8080
    DIRECTOR_V0_VTAG: VersionTag = Field(
        "v0", description="Director-v0 service API's version tag"
    )

    @cached_property
    def endpoint(self) -> str:
        return AnyHttpUrl.build(
            scheme="http",
            host=self.DIRECTOR_V0_HOST,
            port=f"{self.DIRECTOR_V0_PORT}",
            path=f"/{self.DIRECTOR_V0_VTAG}",
        )


class CelerySettings(BaseCelerySettings):
    DIRECTOR_V2_CELERY_ENABLED: bool = Field(
        True, description="Enables/Disables connection with service"
    )
    CELERY_PUBLICATION_TIMEOUT: int = 60


class DynamicServicesSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED: bool = Field(
        True, description="Enables/Disables connection with service"
    )


class PGSettings(PostgresSettings):
    DIRECTOR_V2_POSTGRES_ENABLED: bool = Field(
        True, description="Enables/Disables connection with service"
    )


class CelerySchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_CELERY_SCHEDULER_ENABLED: bool = Field(
        True,
        description="Enables/Disables the scheduler",
    )


class DaskSchedulerSettings(BaseCustomSettings):
    DIRECTOR_V2_DASK_SCHEDULER_ENABLED: bool = True


class AppSettings(BaseCustomSettings, MixinLoggingSettings):
    # DOCKER
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_BOOT_TARGET: Optional[BuildTargetEnum]

    LOG_LEVEL: LogLevel = Field(
        LogLevel.INFO.value,
        env=["DIRECTOR_V2_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    # CELERY submodule
    CELERY: CelerySettings

    # DIRECTOR submodule
    DIRECTOR_V0: DirectorV0Settings

    # Dynamic Services submodule
    DYNAMIC_SERVICES: DynamicServicesSettings

    # POSTGRES
    POSTGRES: PGSettings

    # STORAGE
    STORAGE_ENDPOINT: str = Field("storage:8080", env="STORAGE_ENDPOINT")

    # for passing self-signed certificate to spawned services
    # TODO: fix these variables once the timeout-minutes: 30 is able to start dynamic services
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_ID: str = ""
    DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME: str = ""
    DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME: str = ""

    # extras
    EXTRA_HOSTS_SUFFIX: str = Field("undefined", env="EXTRA_HOSTS_SUFFIX")
    PUBLISHED_HOSTS_NAME: str = Field("", env="PUBLISHED_HOSTS_NAME")
    SWARM_STACK_NAME: str = Field("undefined-please-check", env="SWARM_STACK_NAME")

    #
    NODE_SCHEMA_LOCATION: str = Field(
        f"{API_ROOT}/{api_vtag}/schemas/node-meta-v0.0.1.json",
        description="used when in devel mode vs release mode",
    )

    #
    SIMCORE_SERVICES_NETWORK_NAME: Optional[str] = Field(
        None,
        description="used to find the right network name",
    )
    SIMCORE_SERVICES_PREFIX: Optional[str] = Field(
        "simcore/services",
        description="useful when developing with an alternative registry namespace",
    )

    # traefik
    TRAEFIK_SIMCORE_ZONE: str = Field("internal_simcore_stack")

    # monitoring
    MONITORING_ENABLED: bool = False

    # fastappi app settings
    DIRECTOR_V2_DEBUG: bool = False

    # ptvsd settings
    DIRECTOR_V2_REMOTE_DEBUG_PORT: PortInt = 3000

    CLIENT_REQUEST: ClientRequestSettings

    CELERY_SCHEDULER: CelerySchedulerSettings

    DASK_SCHEDULER: DaskSchedulerSettings

    @validator("LOG_LEVEL", pre=True)
    @classmethod
    def _validate_loglevel(cls, value) -> str:
        return cls.validate_log_level(value)
