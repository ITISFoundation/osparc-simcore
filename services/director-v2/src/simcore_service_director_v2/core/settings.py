# pylint: disable=no-self-argument
# pylint: disable=no-self-use
import logging
from enum import Enum
from typing import Optional

from models_library.settings.celery import CeleryConfig
from models_library.settings.postgres import PostgresSettings
from pydantic import (
    BaseSettings,
    Field,
    SecretStr,
    conint,
    constr,
    root_validator,
    validator,
)

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


PortInt = conint(gt=0, lt=65535)


class BootModeEnum(str, Enum):
    DEFAULT = "default"
    DEBUG = "debug-ptvsd"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class CommonConfig:
    case_sensitive = False
    env_file = ".env"  # SEE https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support


class ApiServiceSettings(BaseSettings):
    """ Settings needed to connect a osparc-simcore service API"""

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


class PGSettings(PostgresSettings):
    enabled: bool = Field(True, description="Enables/Disables connection with service")

    class Config(CommonConfig):
        env_prefix = "POSTGRES_"


class RegistrySettings(BaseSettings):
    """ Settings for docker_registry module """

    enabled: bool = Field(True, description="Enables/Disables connection with service")

    # entrypoint
    ssl: bool = True
    url: str = Field(..., description="URL to the docker registry", env="REGISTRY_URL")

    # auth
    auth: bool = True
    user: Optional[str] = None
    pw: Optional[SecretStr] = None

    @validator("url", pre=True)
    def secure_url(cls, v, values):
        if values["ssl"]:
            if v.startswith("http://"):
                v = v.replace("http://", "https://")
        return v

    @root_validator
    def check_auth_credentials(cls, values):
        if values["auth"]:
            user, pw = values.get("user"), values.get("pw")
            if user is None or pw is None:
                raise ValueError("Cannot authenticate without credentials user, pw")
            if not values["ssl"]:
                raise ValueError("Authentication REQUIRES a secured channel")
        return values

    @property
    def api_url(self) -> str:
        return f"{self.url}/v2"

    class Config(CommonConfig):
        env_prefix = "REGISTRY_"


class AppSettings(BaseSettings):
    @classmethod
    def create_from_env(cls, **settings_kwargs) -> "AppSettings":
        return cls(
            postgres=PostgresSettings(),
            director_v0=DirectorV0Settings(),
            registry=RegistrySettings(),
            celery=CelerySettings.create_from_env(),
            **settings_kwargs,
        )

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

    # CELERY submodule
    celery: CelerySettings

    # DIRECTOR submodule
    director_v0: DirectorV0Settings

    # REGISTRY submodule
    registry: RegistrySettings

    # POSTGRES
    postgres: PGSettings

    # STORAGE
    storage_endpoint: str = Field("storage:8080", env="STORAGE_ENDPOINT")

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

    # SERVICE SERVER (see : https://www.uvicorn.org/settings/)
    host: str = "0.0.0.0"  # nosec
    port: PortInt = 8000
    debug: bool = False  # If True, debug tracebacks should be returned on errors.

    remote_debug_port: PortInt = 3000

    class Config(CommonConfig):
        env_prefix = "DIRECTOR_V2_"
