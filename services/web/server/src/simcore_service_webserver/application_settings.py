import logging
from functools import cached_property
from typing import Any, Dict, List, Optional

from aiohttp import web
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from pydantic import validator
from pydantic.fields import Field, ModelField
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
from .garbage_collector_settings import GarbageCollectorSettings
from .login.settings import LoginSettings
from .resource_manager.settings import ResourceManagerSettings
from .rest_settings import RestSettings
from .scicrunch.settings import SciCrunchSettings
from .session_settings import SessionSettings
from .statics_settings import FrontEndAppSettings, StaticWebserverModuleSettings
from .storage_settings import StorageSettings
from .studies_dispatcher.settings import StudiesDispatcherSettings
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
    SC_BOOT_MODE: Optional[BootModeEnum] = None
    SC_HEALTHCHECK_INTERVAL: Optional[int] = None
    SC_HEALTHCHECK_RETRY: Optional[int] = None
    SC_USER_ID: Optional[int] = None
    SC_USER_NAME: Optional[str] = None

    # RUNTIME  -----------------------------------------------------------
    # settings defined from environs defined when container runs
    # NOTE: keep alphabetically if possible
    AIODEBUG_SLOW_DURATION_SECS: float = 0

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
    # TODO: find a better name!?
    WEBSERVER_SERVER_HOST: str = Field(
        "0.0.0.0", description="hostname to serve within the container"
    )
    WEBSERVER_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    WEBSERVER_SESSION: SessionSettings = Field(
        auto_default_from_env=True, description="sesion module"
    )

    # PLUGINS ----------------

    WEBSERVER_ACTIVITY: Optional[PrometheusSettings] = Field(
        auto_default_from_env=True,
        description="activity plugin",
    )
    WEBSERVER_CATALOG: Optional[CatalogSettings] = Field(
        auto_default_from_env=True, description="catalog service client's plugin"
    )
    WEBSERVER_COMPUTATION: Optional[RabbitSettings] = Field(
        auto_default_from_env=True, description="computation plugin"
    )
    # TODO: Shall be required
    WEBSERVER_DB: Optional[PostgresSettings] = Field(
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

    WEBSERVER_FRONTEND: Optional[FrontEndAppSettings] = Field(
        auto_default_from_env=True, description="front-end static settings"
    )

    WEBSERVER_GARBAGE_COLLECTOR: Optional[GarbageCollectorSettings] = Field(
        auto_default_from_env=True, description="garbage collector plugin"
    )

    WEBSERVER_LOGIN: Optional[LoginSettings] = Field(
        auto_default_from_env=True, description="login plugin"
    )
    WEBSERVER_REDIS: Optional[RedisSettings] = Field(auto_default_from_env=True)

    WEBSERVER_REST: Optional[RestSettings] = Field(
        auto_default_from_env=True, description="rest api plugin"
    )

    WEBSERVER_RESOURCE_MANAGER: ResourceManagerSettings = Field(
        auto_default_from_env=True, description="resource_manager plugin"
    )
    WEBSERVER_S3: Optional[S3Settings] = Field(auto_default_from_env=True)
    WEBSERVER_SCICRUNCH: Optional[SciCrunchSettings] = Field(
        auto_default_from_env=True, description="scicrunch plugin"
    )
    WEBSERVER_STATICWEB: Optional[StaticWebserverModuleSettings] = Field(
        auto_default_from_env=True, description="static-webserver service plugin"
    )
    WEBSERVER_STORAGE: Optional[StorageSettings] = Field(
        auto_default_from_env=True, description="storage service client's plugin"
    )
    WEBSERVER_STUDIES_DISPATCHER: Optional[StudiesDispatcherSettings] = Field(
        auto_default_from_env=True, description="studies dispatcher plugin"
    )

    WEBSERVER_TRACING: Optional[TracingSettings] = Field(
        auto_default_from_env=True, description="tracing plugin"
    )

    # These plugins only require (for the moment) an entry to toggle between enabled/disabled
    WEBSERVER_CLUSTERS: bool = True
    WEBSERVER_GROUPS: bool = True
    WEBSERVER_META_MODELING: bool = True
    WEBSERVER_PRODUCTS: bool = True
    WEBSERVER_PROJECTS: bool = True
    WEBSERVER_PUBLICATIONS: bool = True
    WEBSERVER_REMOTE_DEBUG: bool = True
    WEBSERVER_SOCKETIO: bool = True
    WEBSERVER_TAGS: bool = True
    WEBSERVER_USERS: bool = True
    WEBSERVER_VERSION_CONTROL: bool = True

    @validator(
        # List of plugins under-development (keep up-to-date)
        # TODO: consider mark as dev-feature in field extras of Config attr.
        # Then they can be automtically advertised
        "WEBSERVER_META_MODELING",
        "WEBSERVER_VERSION_CONTROL",
        "WEBSERVER_CLUSTERS",
        pre=True,
        always=True,
    )
    @classmethod
    def enable_only_if_dev_features_allowed(cls, v, values, field: ModelField):
        """Ensures that plugins 'under development' get programatically
        disabled if WEBSERVER_DEV_FEATURES_ENABLED=False
        """
        if values["WEBSERVER_DEV_FEATURES_ENABLED"]:
            return v
        if v:
            log.warning("%s still under development and will be disabled.", field.name)
        return None if field.allow_none else False

    class Config(BaseCustomSettings.Config):
        # NOTE: FutureWarning: aliases are no longer used by BaseSettings to define which environment variables to read.
        #       Instead use the "env" field setting. See https://pydantic-docs.helpmanual.io/usage/settings/#environment-variable-names
        # NOTE: These alias are ONLY used in export, not in constructor
        fields = {
            "SC_VCS_URL": "vcs_url",
            "SC_VCS_REF": "vcs_ref",
            "SC_BUILD_DATE": "build_date",
            "SWARM_STACK_NAME": "stack_name",
        }
        alias_generator = lambda s: s.lower()

    @cached_property
    def log_level(self) -> int:
        return getattr(logging, self.WEBSERVER_LOG_LEVEL.upper())

    @validator("WEBSERVER_LOG_LEVEL")
    @classmethod
    def valid_log_level(cls, value) -> str:
        return cls.validate_log_level(value)

    # HELPERS  --------------------------------------------------------

    def is_enabled(self, field_name: str) -> bool:
        return bool(getattr(self, field_name, None))

    def _get_disabled_public_plugins(self) -> List[str]:
        plugins_disabled = []
        # NOTE: this list is limited for security reasons. An unbounded list
        # might reveal critical info on the settings of a deploy to the client.
        # TODO: more reliable definition of a "plugin" and whether it can be advertised or not
        # (extra var? e.g. Field( ... , x_advertise_plugin=True))
        PUBLIC_PLUGIN_CANDIDATES = {
            "WEBSERVER_CLUSTERS",
            "WEBSERVER_EXPORTER",
            "WEBSERVER_META_MODELING",
            "WEBSERVER_SCICRUNCH",
            "WEBSERVER_VERSION_CONTROL",
        }
        for field_name in PUBLIC_PLUGIN_CANDIDATES:
            if not self.is_enabled(field_name):
                plugins_disabled.append(field_name)
        return plugins_disabled

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
        data["plugins_disabled"] = self._get_disabled_public_plugins()

        # Alias in addition MUST be camelcase here
        return {snake_to_camel(k): v for k, v in data.items()}


def setup_settings(app: web.Application) -> ApplicationSettings:
    app[APP_SETTINGS_KEY] = settings = ApplicationSettings.create_from_envs()
    log.info("Captured app settings:\n%s", app[APP_SETTINGS_KEY].json(indent=1))
    return settings


def get_settings(app: web.Application) -> ApplicationSettings:
    return app[APP_SETTINGS_KEY]
