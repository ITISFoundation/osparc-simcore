# pylint: disable=no-self-argument
# pylint: disable=no-self-use
import logging
from pathlib import Path
from typing import Optional

from models_library.basic_types import BootModeEnum, PortInt
from models_library.services import SERVICE_NETWORK_RE
from models_library.settings.base import BaseCustomSettings
from models_library.settings.celery import CeleryConfig
from models_library.settings.http_clients import ClientRequestSettings
from models_library.settings.postgres import PostgresSettings
from pydantic import BaseSettings, Field, PositiveFloat, PositiveInt, constr, validator
from settings_library.docker_registry import RegistrySettings

MINS = 60
API_ROOT: str = "api"
APP_REGISTRY_CACHE_DATA_KEY: str = __name__ + "_registry_cache_data"

SERVICE_RUNTIME_SETTINGS: str = "simcore.service.settings"
SERVICE_REVERSE_PROXY_SETTINGS: str = "simcore.service.reverse-proxy-settings"
SERVICE_RUNTIME_BOOTSETTINGS: str = "simcore.service.bootsettings"

ORG_LABELS_TO_SCHEMA_LABELS = {
    "org.label-schema.build-date": "build_date",
    "org.label-schema.vcs-ref": "vcs_ref",
    "org.label-schema.vcs-url": "vcs_url",
}

DYNAMIC_SIDECAR_DOCKER_IMAGE_RE = (
    r"(^(local|itisfoundation)/)?(dynamic-sidecar):([\w]+)"
)

VersionTag = constr(regex=r"^v\d$")


class CommonConfig:
    case_sensitive = False
    env_file = ".env"  # SEE https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support


class ApiServiceSettings(BaseSettings):
    """Settings needed to connect a osparc-simcore service API"""

    enabled: bool = Field(True, description="Enables/Disables connection with service")

    host: str
    port: PortInt = 8000
    vtag: VersionTag = "v0"

    def base_url(self, include_tag=False) -> str:
        url = f"http://{self.host}:{self.port}"
        if include_tag:
            url += f"/{self.vtag}"
        return url


class CelerySettings(CeleryConfig):
    enabled: bool = Field(True, description="Enables/Disables connection with service")

    class Config(CommonConfig):
        env_prefix = "CELERY_"


class DirectorV0Settings(ApiServiceSettings):
    class Config(CommonConfig):
        env_prefix = "DIRECTOR_"


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
    DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT: PositiveInt = Field(
        15,
        description=(
            "the default timeout each request to the dynamic-sidecar API in seconds; as per "
            "design, all requests should answer quite quickly, in theory a few seconds or less"
        ),
    )
    DYNAMIC_SIDECAR_TIMEOUT_FETCH_DYNAMIC_SIDECAR_NODE_ID: PositiveFloat = Field(
        60,
        description=(
            "When starting the dynamic-sidecar proxy, the NodeID of the dynamic-sidecar container "
            "is required. If something goes wrong timeout and do not wait forever in a loop. "
            "This is used to monitor the status of the service via aiodocker and not http requests "
            "twards the dynamic-sidecar, as is the case with the above timeout field."
        ),
    )

    TRAEFIK_SIMCORE_ZONE: str = Field(
        ...,
        description="Names the traefik zone for services that must be accessible from platform http entrypoint",
    )

    DYNAMIC_SIDECAR_TRAEFIK_VERSION: str = Field(
        "v2.2.1",
        description="current version of the Traefik image to be pulled and used from dockerhub",
    )

    SWARM_STACK_NAME: str = Field(
        ...,
        description="in case there are several deployments on the same docker swarm, it is attached as a label on all spawned services",
    )

    REGISTRY: RegistrySettings


class DynamicServicesMonitoringSettings(BaseCustomSettings):
    DIRECTOR_V2_MONITORING_ENABLED: bool = True

    DIRECTOR_V2_MONITOR_INTERVAL_SECONDS: PositiveFloat = Field(
        5.0, description="interval at which the monitor cycle is repeated"
    )

    DIRECTOR_V2_MONITOR_MAX_STATUS_API_DURATION: PositiveFloat = Field(
        1.0,
        description=(
            "when requesting the status of a service this is the "
            "maximum amount of time the request can last"
        ),
    )


class DynamicServicesSettings(BaseCustomSettings):
    DIRECTOR_V2_DYNAMIC_SERVICES_ENABLED: bool = Field(
        True, description="Enables/Disables connection with service"
    )

    # dynamic sidecar
    DYNAMIC_SIDECAR: DynamicSidecarSettings

    # dynamic services monitoring
    MONITORING: DynamicServicesMonitoringSettings


class PGSettings(PostgresSettings):
    enabled: bool = Field(True, description="Enables/Disables connection with service")

    class Config(CommonConfig, PostgresSettings.Config):
        env_prefix = "POSTGRES_"


class CelerySchedulerSettings(BaseSettings):
    enabled: bool = Field(
        True,
        description="Enables/Disables the scheduler",
        env="DIRECTOR_V2_SCHEDULER_ENABLED",
    )

    class Config(CommonConfig):
        pass


class AppSettings(BaseSettings):
    @classmethod
    def create_from_env(cls, **settings_kwargs) -> "AppSettings":
        return cls(
            postgres=PGSettings(),
            director_v0=DirectorV0Settings(),
            celery=CelerySettings.create_from_env(),
            dynamic_services=DynamicServicesSettings(
                DYNAMIC_SIDECAR=DynamicSidecarSettings(REGISTRY=RegistrySettings()),
                MONITORING=DynamicServicesMonitoringSettings(),
            ),
            client_request=ClientRequestSettings(),
            scheduler=CelerySchedulerSettings(),
            **settings_kwargs,
        )

    # DOCKER
    boot_mode: Optional[BootModeEnum] = Field(..., env="SC_BOOT_MODE")

    # LOGGING
    log_level_name: str = Field("DEBUG", env="LOG_LEVEL")

    @validator("log_level_name")
    @classmethod
    def match_logging_level(cls, value) -> str:
        try:
            getattr(logging, value.upper())
        except AttributeError as err:
            raise ValueError(f"{value.upper()} is not a valid level") from err
        return value.upper()

    @property
    def loglevel(self) -> int:
        return getattr(logging, self.log_level_name)

    # CELERY submodule
    celery: CelerySettings

    # DIRECTOR submodule
    director_v0: DirectorV0Settings

    # Dynamic Services submodule
    dynamic_services: DynamicServicesSettings

    # POSTGRES
    postgres: PGSettings

    # STORAGE
    storage_endpoint: str = Field("storage:8080", env="STORAGE_ENDPOINT")

    # monitoring
    monitoring_enabled: str = Field(False, env="MONITORING_ENABLED")

    # fastappi app settings
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    # ptvsd settings
    remote_debug_port: PortInt = 3000

    client_request: ClientRequestSettings

    scheduler: CelerySchedulerSettings

    class Config(CommonConfig):
        env_prefix = ""
