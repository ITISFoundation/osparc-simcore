import logging
from typing import Any, Dict, Optional

from aiohttp import web
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from pydantic import Field, validator
from pydantic.types import SecretBytes
from settings_library.base import BaseCustomSettings
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings
from settings_library.prometheus import PrometheusSettings
from settings_library.redis import RedisSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT

from ._constants import APP_SETTINGS_KEY
from ._meta import API_VERSION, API_VTAG, APP_NAME

# from .activity.settings import ActivitySettings
from .catalog_settings import CatalogSettings
from .director.settings import DirectorSettings
from .director_v2_settings import DirectorV2Settings
from .exporter.settings import ExporterSettings

# from .email_settings import SmtpSettings
from .login.settings import LoginSettings
from .resource_manager.settings import ResourceManagerSettings
from .scicrunch.settings import SciCrunchSettings
from .storage_settings import StorageSettings
from .utils import snake_to_camel

# from .tracing_settings import TracingSettings


log = logging.getLogger(__name__)


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: Optional[str] = None
    SC_BUILD_TARGET: Optional[BuildTargetEnum] = None
    SC_VCS_REF: Optional[str] = None
    SC_VCS_URL: Optional[str] = None

    # @Dockerfile
    SC_BOOT_MODE: Optional[BootModeEnum]
    SC_HEALTHCHECK_INTERVAL: Optional[int] = None
    SC_HEALTHCHECK_RETRY: Optional[int] = None
    SC_USER_ID: Optional[int] = None
    SC_USER_NAME: Optional[str] = None

    # RUNTIME  -----------------------------------------------------------
    # settings defined from environs defined when container runs
    # NOTE: keep alphabetically if possible

    SWARM_STACK_NAME: Optional[str] = Field(
        None, description="Stack name defined upon deploy (see main Makefile)"
    )

    # WEBSERVER_ACTIVITY: Optional[ActivitySettings]
    WEBSERVER_CATALOG: Optional[CatalogSettings] = Field(auto_default_from_env=True)
    WEBSERVER_DEV_FEATURES_ENABLED: bool = Field(
        False,
        description="Enables development features. WARNING: make sure it is disabled in production .env file!",
    )
    WEBSERVER_DIRECTOR_V2: Optional[DirectorV2Settings] = Field(
        auto_default_from_env=True
    )
    WEBSERVER_DIRECTOR: Optional[DirectorSettings] = Field(auto_default_from_env=True)
    WEBSERVER_EMAIL: Optional[SMTPSettings] = Field(auto_default_from_env=True)
    WEBSERVER_EXPORTER: Optional[ExporterSettings] = Field(auto_default_from_env=True)
    WEBSERVER_LOG_LEVEL: LogLevel = Field(
        LogLevel.WARNING.value,
        env=["WEBSERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    WEBSERVER_LOGIN: Optional[LoginSettings] = Field(auto_default_from_env=True)
    WEBSERVER_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    WEBSERVER_POSTGRES: PostgresSettings = Field(auto_default_from_env=True)
    WEBSERVER_PROMETHEUS: Optional[PrometheusSettings] = Field(
        auto_default_from_env=True
    )
    WEBSERVER_REDIS: Optional[RedisSettings] = Field(auto_default_from_env=True)
    WEBSERVER_RESOURCE_MANAGER: Optional[ResourceManagerSettings] = Field(
        auto_default_from_env=True
    )
    WEBSERVER_S3: Optional[S3Settings] = Field(auto_default_from_env=True)
    WEBSERVER_SCICRUNCH: Optional[SciCrunchSettings] = Field(auto_default_from_env=True)
    WEBSERVER_SESSION_SECRET_KEY: SecretBytes = Field(
        ...,
        description="Secret key to encrypt cookies",
        min_length=32,
    )
    WEBSERVER_STORAGE: Optional[StorageSettings] = Field(auto_default_from_env=True)
    WEBSERVER_STUDIES_ACCESS_ENABLED: bool
    WEBSERVER_TRACING: Optional[TracingSettings] = Field(auto_default_from_env=True)

    @validator("WEBSERVER_SESSION_SECRET_KEY", pre=True)
    @classmethod
    def truncate_session_key(cls, v):
        return v[:32]

    class Config(BaseCustomSettings.Config):
        fields = {
            "SC_VCS_URL": "vcs_url",
            "SC_VCS_REF": "vcs_ref",
            "SC_BUILD_DATE": "build_date",
            "SWARM_STACK_NAME": "stack_name",
        }
        alias_generator = lambda s: s.lower()

    # HELPERS  --------------------------------------------------------

    def public_dict(self) -> Dict[str, Any]:
        """Data publicaly available"""
        return self.dict(
            include={
                "APP_NAME",
                "API_VERSION",
                "SC_VCS_URL",
                "SC_VCS_REF",
                "SC_BUILD_DATE",
            },
            exclude_none=True,
            by_alias=True,
        )

    def to_client_statics(self) -> Dict[str, Any]:
        data = self.dict(
            include={
                "APP_NAME",
                "API_VERSION",
                "SC_VCS_URL",
                "SC_VCS_REF",
                "SC_BUILD_DATE",
                "SWARM_STACK_NAME",
            },
            exclude_none=True,
            by_alias=True,
        )
        # Alias MUST be camelcase here
        return {snake_to_camel(k): v for k, v in data.items()}


def setup_settings(app: web.Application) -> ApplicationSettings:
    app[APP_SETTINGS_KEY] = settings = ApplicationSettings.create_from_envs()
    log.info("Captured app settings:\n%s", app[APP_SETTINGS_KEY].json(indent=1))
    return settings


def get_settings(app: web.Application) -> ApplicationSettings:
    return app[APP_SETTINGS_KEY]
