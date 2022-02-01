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
from pydantic.types import SecretBytes, SecretStr
from settings_library.base import BaseCustomSettings
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings
from settings_library.prometheus import PrometheusSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.s3 import S3Settings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT

from ._constants import APP_SETTINGS_KEY
from ._meta import API_VERSION, API_VTAG, APP_NAME
from .catalog_settings import CatalogSettings
from .diagnostics_settings import DiagnosticsSettings
from .director.settings import DirectorSettings
from .director_v2_settings import DirectorV2Settings
from .exporter.settings import ExporterSettings
from .login.settings import LoginSettings
from .resource_manager.settings import ResourceManagerSettings
from .scicrunch.settings import SciCrunchSettings
from .storage_settings import StorageSettings
from .utils import snake_to_camel

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

    WEBSERVER_DEV_FEATURES_ENABLED: bool = Field(
        False,
        description="Enables development features. WARNING: make sure it is disabled in production .env file!",
    )
    WEBSERVER_LOG_LEVEL: LogLevel = Field(
        LogLevel.WARNING.value,
        env=["WEBSERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )
    WEBSERVER_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    WEBSERVER_SESSION_SECRET_KEY: SecretBytes = Field(
        ...,
        description="Secret key to encrypt cookies",
        min_length=32,
    )
    WEBSERVER_STUDIES_ACCESS_ENABLED: bool

    # PLUGINS ----------------

    WEBSERVER_ACTIVITY: Optional[PrometheusSettings] = Field(
        auto_default_from_env=True, description="activity plugin"
    )
    WEBSERVER_CATALOG: Optional[CatalogSettings] = Field(
        auto_default_from_env=True, description="catalog service client's plugin"
    )
    WEBSERVER_COMPUTATION: Optional[RabbitSettings] = Field(
        auto_default_from_env=True, description="computation plugin"
    )
    WEBSERVER_DB: PostgresSettings = Field(
        auto_default_from_env=True, description="database plugin"
    )
    WEBSERVER_DIAGNOSTICS: Optional[DiagnosticsSettings] = Field(
        auto_default_from_env=True, description="diagnostics plugin"
    )
    WEBSERVER_DIRECTOR_V2: Optional[DirectorV2Settings] = Field(
        auto_default_from_env=True, description="director-v2 service client's plugin"
    )
    WEBSERVER_DIRECTOR: Optional[DirectorSettings] = Field(
        auto_default_from_env=True, description="director service client's plugin"
    )
    WEBSERVER_EMAIL: Optional[SMTPSettings] = Field(
        auto_default_from_env=True, description="email plugin"
    )
    WEBSERVER_EXPORTER: Optional[ExporterSettings] = Field(
        auto_default_from_env=True, description="exporter plugin"
    )
    WEBSERVER_LOGIN: Optional[LoginSettings] = Field(
        auto_default_from_env=True, description="login plugin"
    )
    WEBSERVER_REDIS: Optional[RedisSettings] = Field(auto_default_from_env=True)
    WEBSERVER_RESOURCE_MANAGER: Optional[ResourceManagerSettings] = Field(
        auto_default_from_env=True, description="resource_manager plugin"
    )
    WEBSERVER_S3: Optional[S3Settings] = Field(auto_default_from_env=True)
    WEBSERVER_SCICRUNCH: Optional[SciCrunchSettings] = Field(
        auto_default_from_env=True, description="scicrunch plugin"
    )
    WEBSERVER_STORAGE: Optional[StorageSettings] = Field(
        auto_default_from_env=True, description="storage service client's plugin"
    )
    WEBSERVER_TRACING: Optional[TracingSettings] = Field(
        auto_default_from_env=True, description="tracing plugin"
    )

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


def convert_to_app_config(app_settings: ApplicationSettings) -> Dict[str, Any]:
    """Maps current ApplicationSettings object into former trafaret-based config"""

    cfg = {
        "version": "1.0",
        "main": {
            "host": "0.0.0.0",
            "port": app_settings.WEBSERVER_PORT,
            "log_level": f"{app_settings.WEBSERVER_LOG_LEVEL}",
            "testing": False,  # TODO: deprecate!
            "studies_access_enabled": 1
            if app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED
            else 0,
        },
        "tracing": {
            "enabled": 1 if app_settings.WEBSERVER_TRACING is not None else 0,
            "zipkin_endpoint": f"{getattr(app_settings.WEBSERVER_TRACING, 'TRACING_ZIPKIN_ENDPOINT', None)}",
        },
        "socketio": {"enabled": True},
        "director": {
            "enabled": app_settings.WEBSERVER_DIRECTOR is not None,
            "host": getattr(app_settings.WEBSERVER_DIRECTOR, "DIRECTOR_HOST", None),
            "port": getattr(app_settings.WEBSERVER_DIRECTOR, "DIRECTOR_PORT", None),
            "version": getattr(app_settings.WEBSERVER_DIRECTOR, "DIRECTOR_VTAG", None),
        },
        "db": {
            "postgres": {
                "database": getattr(app_settings.WEBSERVER_DB, "POSTGRES_DB", None),
                "endpoint": f"{getattr(app_settings.WEBSERVER_DB, 'POSTGRES_HOST', None)}:{getattr(app_settings.WEBSERVER_DB, 'POSTGRES_PORT', None)}",
                "host": getattr(app_settings.WEBSERVER_DB, "POSTGRES_HOST", None),
                "maxsize": getattr(app_settings.WEBSERVER_DB, "POSTGRES_MAXSIZE", None),
                "minsize": getattr(app_settings.WEBSERVER_DB, "POSTGRES_MINSIZE", None),
                "password": getattr(
                    app_settings.WEBSERVER_DB, "POSTGRES_PASSWORD", SecretStr("")
                ).get_secret_value(),
                "port": getattr(app_settings.WEBSERVER_DB, "POSTGRES_PORT", None),
                "user": getattr(app_settings.WEBSERVER_DB, "POSTGRES_USER", None),
            },
            "enabled": app_settings.WEBSERVER_DB is not None,
        },
        "resource_manager": {
            "enabled": (
                app_settings.WEBSERVER_REDIS is not None
                and app_settings.WEBSERVER_RESOURCE_MANAGER is not None
            ),
            "resource_deletion_timeout_seconds": getattr(
                app_settings.WEBSERVER_RESOURCE_MANAGER,
                "RESOURCE_MANAGER_RESOURCE_TTL_S",
                None,
            ),
            "garbage_collection_interval_seconds": getattr(
                app_settings.WEBSERVER_RESOURCE_MANAGER,
                "RESOURCE_MANAGER_GARBAGE_COLLECTION_INTERVAL_S",
                None,
            ),
            "redis": {
                "enabled": app_settings.WEBSERVER_REDIS is not None,
                "host": getattr(app_settings.WEBSERVER_REDIS, "REDIS_HOST", None),
                "port": getattr(app_settings.WEBSERVER_REDIS, "REDIS_PORT", None),
            },
        },
        "login": {
            "enabled": app_settings.WEBSERVER_LOGIN is not None,
            "registration_invitation_required": 1
            if getattr(
                app_settings.WEBSERVER_LOGIN,
                "LOGIN_REGISTRATION_INVITATION_REQUIRED",
                None,
            )
            else 0,
            "registration_confirmation_required": 1
            if getattr(
                app_settings.WEBSERVER_LOGIN,
                "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED",
                None,
            )
            else 0,
        },
        "smtp": {
            "sender": getattr(app_settings.WEBSERVER_EMAIL, "SMTP_SENDER", None),
            "host": getattr(app_settings.WEBSERVER_EMAIL, "SMTP_HOST", None),
            "port": getattr(app_settings.WEBSERVER_EMAIL, "SMTP_PORT", None),
            "tls": int(getattr(app_settings.WEBSERVER_EMAIL, "SMTP_TLS_ENABLED", 0)),
            "username": str(
                getattr(app_settings.WEBSERVER_EMAIL, "SMTP_USERNAME", None)
            ),
            "password": str(
                getattr(app_settings.WEBSERVER_EMAIL, "SMTP_PASSWORD", None)
                and getattr(
                    app_settings.WEBSERVER_EMAIL, "SMTP_PASSWORD", SecretStr("")
                ).get_secret_value()
            ),
        },
        "storage": {
            "enabled": app_settings.WEBSERVER_STORAGE is not None,
            "host": getattr(app_settings.WEBSERVER_STORAGE, "STORAGE_HOST", None),
            "port": getattr(app_settings.WEBSERVER_STORAGE, "STORAGE_PORT", None),
            "version": getattr(app_settings.WEBSERVER_STORAGE, "STORAGE_VTAG", None),
        },
        "catalog": {
            "enabled": app_settings.WEBSERVER_CATALOG is not None,
            "host": getattr(app_settings.WEBSERVER_CATALOG, "CATALOG_HOST", None),
            "port": getattr(app_settings.WEBSERVER_CATALOG, "CATALOG_PORT", None),
            "version": getattr(app_settings.WEBSERVER_CATALOG, "CATALOG_VTAG", None),
        },
        "rest": {"version": app_settings.API_VTAG, "enabled": True},
        "projects": {"enabled": True},
        "session": {
            "secret_key": app_settings.WEBSERVER_SESSION_SECRET_KEY.get_secret_value()
        },
        "activity": {
            "enabled": app_settings.WEBSERVER_ACTIVITY is not None,
            "prometheus_host": getattr(app_settings.WEBSERVER_ACTIVITY, "origin", None),
            "prometheus_port": getattr(
                app_settings.WEBSERVER_ACTIVITY, "PROMETHEUS_PORT", None
            ),
            "prometheus_api_version": getattr(
                app_settings.WEBSERVER_ACTIVITY, "PROMETHEUS_VTAG", None
            ),
        },
        "clusters": {"enabled": True},
        "computation": {"enabled": app_settings.WEBSERVER_COMPUTATION is not None},
        "diagnostics": {"enabled": app_settings.WEBSERVER_DIAGNOSTICS is not None},
        "director-v2": {"enabled": app_settings.WEBSERVER_DIRECTOR_V2 is not None},
        "exporter": {"enabled": app_settings.WEBSERVER_EXPORTER is not None},
        "groups": {"enabled": True},
        "meta_modeling": {"enabled": True},
        "products": {"enabled": True},
        "publications": {"enabled": True},
        "remote_debug": {"enabled": True},
        "security": {"enabled": True},
        "statics": {"enabled": True},
        "studies_access": {
            "enabled": True
        },  # app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED did not apply
        "studies_dispatcher": {
            "enabled": True  # app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED did not apply
        },
        "tags": {"enabled": True},
        "users": {"enabled": True},
        "version_control": {"enabled": True},
    }

    return cfg
