# pylint: disable=no-self-argument
# pylint: disable=no-self-use
import logging
from enum import Enum, unique
from typing import Optional

from models_library.basic_types import BootModeEnum, PortInt
from models_library.settings.celery import CeleryConfig
from models_library.settings.http_clients import ClientRequestSettings
from models_library.settings.postgres import PostgresSettings
from pydantic import BaseSettings, Field, constr, validator

from ..meta import api_vtag

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


@unique
class ServiceType(Enum):
    """
    Used to filter out services spawned by this service in the stack.
    The version was added to distinguish from the ones spawned by director-v0
    These values are attached to the dynamic-sidecar and its relative proxy.
    """

    MAIN: str = f"main-{api_vtag}"
    DEPENDENCY: str = f"dependency-{api_vtag}"


class CommonConfig:
    case_sensitive = False
    env_file = ".env"  # SEE https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support


class ApiServiceSettings(BaseSettings):
    """Settings needed to connect a osparc-simcore service API"""

    enabled: bool = Field(True, description="Enables/Disables connection with service")

    host: str
    port: PortInt = 8000
    vtag: constr(regex=r"^v\d$") = "v0"

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


class DynamicServicesSettings(BaseSettings):
    enabled: bool = Field(True, description="Enables/Disables connection with service")

    class Config(CommonConfig):
        pass


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
            dynamic_services=DynamicServicesSettings(),
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

    # caching registry and TTL (time-to-live)
    # TODO: fix these variables once the director-v2 is able to start dynamic services
    registry_caching: bool = Field(True, env="DIRECTOR_V2_REGISTRY_CACHING")
    registry_caching_ttl: int = Field(15 * MINS, env="DIRECTOR_V2_REGISTRY_CACHING_TTL")

    # for passing self-signed certificate to spawned services
    # TODO: fix these variables once the director-v2 is able to start dynamic services
    self_signed_ssl_secret_id: str = Field(
        "", env="DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_ID"
    )
    self_signed_ssl_secret_name: str = Field(
        "", env="DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME"
    )
    self_signed_ssl_filename: str = Field(
        "", env="DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME"
    )

    # extras
    extra_hosts_suffix: str = Field("undefined", env="EXTRA_HOSTS_SUFFIX")
    published_hosts_name: str = Field("", env="PUBLISHED_HOSTS_NAME")
    swarm_stack_name: str = Field("undefined-please-check", env="SWARM_STACK_NAME")

    #
    node_schema_location: str = Field(
        f"{API_ROOT}/{api_vtag}/schemas/node-meta-v0.0.1.json",
        description="used when in devel mode vs release mode",
        env="NODE_SCHEMA_LOCATION",
    )

    #
    simcore_services_network_name: Optional[str] = Field(
        None,
        description="used to find the right network name",
        env="SIMCORE_SERVICES_NETWORK_NAME",
    )
    simcore_services_prefix: Optional[str] = Field(
        "simcore/services",
        description="useful when developing with an alternative registry namespace",
        env="SIMCORE_SERVICES_PREFIX",
    )

    # traefik
    traefik_simcore_zone: str = Field(
        "internal_simcore_stack", env="TRAEFIK_SIMCORE_ZONE"
    )

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
