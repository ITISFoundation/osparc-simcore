import logging
from enum import Enum
from typing import Optional

from pydantic import BaseSettings, Field, SecretStr, validator
from yarl import URL
from ..__version__ import api_vtag

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


class BootModeEnum(str, Enum):
    debug = "debug-ptvsd"
    production = "production"
    development = "development"


class _CommonConfig:
    case_sensitive = False
    env_file = ".env"  # SEE https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support


class RegistrySettings(BaseSettings):
    auth: bool = False
    user: str = ""
    pw: str = ""
    url: str = ""
    ssl: bool = True

    class Config(_CommonConfig):
        env_prefix = "REGISTRY_"


class PostgresSettings(BaseSettings):
    user: str
    password: SecretStr
    db: str
    host: str
    port: int = 5432

    minsize: int = 10
    maxsize: int = 10

    @property
    def dsn(self) -> URL:
        return URL.build(
            scheme="postgresql",
            user=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            path=f"/{self.db}",
        )

    class Config(_CommonConfig):
        env_prefix = "POSTGRES_"


class TracingSetttings(BaseSettings):
    enabled: bool = True
    zipkin_endpoint: str = "http://jaeger:9411"

    class Config(_CommonConfig):
        env_prefix = "TRACING_"


class AppSettings(BaseSettings):
    @classmethod
    def create_default(cls) -> "AppSettings":
        # This call triggers parsers
        return cls(
            registry=RegistrySettings(),
            postgres=PostgresSettings(),
            tracing=TracingSetttings(),
        )

    # pylint: disable=no-self-use
    # pylint: disable=no-self-argument

    # DOCKER
    boot_mode: Optional[BootModeEnum] = Field(..., env="SC_BOOT_MODE")

    # LOGGING
    log_level_name: str = Field("DEBUG", env="LOG_LEVEL")

    @validator("log_level_name")
    def match_logging_level(cls, value) -> str:
        try:
            getattr(logging, value.upper())
        except AttributeError as err:
            raise ValueError(f"{value.upper()} is not a valid level") from err
        return value.upper()

    @property
    def loglevel(self) -> int:
        return getattr(logging, self.log_level_name)

    # REGISTRY
    registry: RegistrySettings

    # POSTGRES
    postgres: PostgresSettings

    # STORAGE
    storage_endpoint = Field("storage:8080", env="STORAGE_ENDPOINT")

    # caching registry and TTL (time-to-live)
    registry_caching: bool = True
    registry_caching_ttl: int = 15 * MINS

    # for passing self-signed certificate to spawned services
    self_signed_ssl_secret_id: str = ""
    self_signed_ssl_secret_name: str = ""
    self_signed_ssl_filename: str = ""

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

    # tracing
    tracing: TracingSetttings

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "0.0.0.0"  # nosec
    port: int = 8000
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    class Config(_CommonConfig):
        env_prefix = "DIRECTOR_"
