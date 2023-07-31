import logging
from datetime import datetime
from functools import cached_property
from typing import Any

from aiohttp import web
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from models_library.utils.change_case import snake_to_camel
from pydantic import AnyHttpUrl, root_validator, validator
from pydantic.fields import Field, ModelField
from pydantic.types import PositiveInt
from settings_library.base import BaseCustomSettings
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings
from settings_library.prometheus import PrometheusSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT

from ._constants import APP_SETTINGS_KEY
from ._meta import API_VERSION, API_VTAG, APP_NAME
from .catalog.settings import CatalogSettings
from .diagnostics.settings import DiagnosticsSettings
from .director_v2.settings import DirectorV2Settings
from .exporter.settings import ExporterSettings
from .garbage_collector.settings import GarbageCollectorSettings
from .invitations.settings import InvitationsSettings
from .login.settings import LoginSettings
from .projects.settings import ProjectsSettings
from .resource_manager.settings import ResourceManagerSettings
from .resource_usage.settings import ResourceUsageTrackerSettings
from .rest.settings import RestSettings
from .scicrunch.settings import SciCrunchSettings
from .session.settings import SessionSettings
from .statics.settings import FrontEndAppSettings, StaticWebserverModuleSettings
from .storage.settings import StorageSettings
from .studies_dispatcher.settings import StudiesDispatcherSettings

_logger = logging.getLogger(__name__)


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = API_VTAG

    # IMAGE BUILDTIME ------------------------------------------------------
    # @Makefile
    SC_BUILD_DATE: str | None = None
    SC_BUILD_TARGET: BuildTargetEnum | None = None
    SC_VCS_REF: str | None = None
    SC_VCS_URL: str | None = None

    # @Dockerfile
    SC_BOOT_MODE: BootModeEnum | None = None
    SC_HEALTHCHECK_TIMEOUT: PositiveInt | None = Field(
        None,
        description="If a single run of the check takes longer than timeout seconds "
        "then the check is considered to have failed."
        "It takes retries consecutive failures of the health check for the container to be considered unhealthy.",
    )
    SC_USER_ID: int | None = None
    SC_USER_NAME: str | None = None

    # RUNTIME  -----------------------------------------------------------
    # settings defined from environs defined when container runs
    #
    # NOTE: Please keep fields alphabetically if possible
    AIODEBUG_SLOW_DURATION_SECS: float = 0

    # Release information: Passed by the osparc-ops-autodeployer
    SIMCORE_VCS_RELEASE_TAG: str | None = Field(
        default=None,
        description="Name of the tag that makrs this release or None if undefined",
        example="ResistanceIsFutile10",
    )
    SIMCORE_VCS_RELEASE_DATE: datetime | None = Field(
        default=None,
        description="Release date or None if undefined. It corresponds to the tag's creation date",
    )
    SIMCORE_VCS_RELEASE_URL: AnyHttpUrl | None = Field(
        default=None,
        description="URL to release notes",
        example="https://github.com/ITISFoundation/osparc-simcore/releases/tag/staging_ResistanceIsFutile10",
    )

    SWARM_STACK_NAME: str | None = Field(
        None, description="Stack name defined upon deploy (see main Makefile)"
    )

    WEBSERVER_DEV_FEATURES_ENABLED: bool = Field(
        False,
        description="Enables development features. WARNING: make sure it is disabled in production .env file!",
    )
    WEBSERVER_LOGLEVEL: LogLevel = Field(
        LogLevel.WARNING.value,
        env=["WEBSERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
        # NOTE: suffix '_LOGLEVEL' is used overall
    )
    WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        False,
        env=["WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    # TODO: find a better name!?
    WEBSERVER_SERVER_HOST: str = Field(
        "0.0.0.0",  # nosec
        description="host name to serve within the container."
        "NOTE that this different from WEBSERVER_HOST env which is the host seen outside the container",
    )
    WEBSERVER_HOST: str | None = Field(None, env=["WEBSERVER_HOST", "HOST", "HOSTNAME"])
    WEBSERVER_PORT: PortInt = DEFAULT_AIOHTTP_PORT

    WEBSERVER_FRONTEND: FrontEndAppSettings | None = Field(
        auto_default_from_env=True, description="front-end static settings"
    )

    # PLUGINS ----------------

    WEBSERVER_ACTIVITY: PrometheusSettings | None = Field(
        auto_default_from_env=True,
        description="activity plugin",
    )
    WEBSERVER_CATALOG: CatalogSettings | None = Field(
        auto_default_from_env=True, description="catalog service client's plugin"
    )
    # TODO: Shall be required
    WEBSERVER_DB: PostgresSettings | None = Field(
        auto_default_from_env=True, description="database plugin"
    )
    WEBSERVER_DIAGNOSTICS: DiagnosticsSettings | None = Field(
        auto_default_from_env=True, description="diagnostics plugin"
    )
    WEBSERVER_DIRECTOR_V2: DirectorV2Settings | None = Field(
        auto_default_from_env=True, description="director-v2 service client's plugin"
    )
    WEBSERVER_EMAIL: SMTPSettings | None = Field(
        auto_default_from_env=True, description="email plugin"
    )
    WEBSERVER_EXPORTER: ExporterSettings | None = Field(
        auto_default_from_env=True, description="exporter plugin"
    )

    WEBSERVER_GARBAGE_COLLECTOR: GarbageCollectorSettings | None = Field(
        auto_default_from_env=True, description="garbage collector plugin"
    )

    WEBSERVER_INVITATIONS: InvitationsSettings | None = Field(
        auto_default_from_env=True, description="invitations plugin"
    )

    WEBSERVER_LOGIN: LoginSettings | None = Field(
        auto_default_from_env=True, description="login plugin"
    )
    WEBSERVER_REDIS: RedisSettings | None = Field(auto_default_from_env=True)

    WEBSERVER_REST: RestSettings | None = Field(
        auto_default_from_env=True, description="rest api plugin"
    )

    WEBSERVER_RESOURCE_MANAGER: ResourceManagerSettings = Field(
        auto_default_from_env=True, description="resource_manager plugin"
    )
    WEBSERVER_RESOURCE_USAGE_TRACKER: ResourceUsageTrackerSettings | None = Field(
        auto_default_from_env=True,
        description="resource usage tracker service client's plugin",
    )
    WEBSERVER_SCICRUNCH: SciCrunchSettings | None = Field(
        auto_default_from_env=True, description="scicrunch plugin"
    )
    WEBSERVER_SESSION: SessionSettings = Field(
        auto_default_from_env=True, description="session plugin"
    )

    WEBSERVER_STATICWEB: StaticWebserverModuleSettings | None = Field(
        auto_default_from_env=True, description="static-webserver service plugin"
    )
    WEBSERVER_STORAGE: StorageSettings | None = Field(
        auto_default_from_env=True, description="storage service client's plugin"
    )
    WEBSERVER_STUDIES_DISPATCHER: StudiesDispatcherSettings | None = Field(
        auto_default_from_env=True, description="studies dispatcher plugin"
    )

    WEBSERVER_TRACING: TracingSettings | None = Field(
        auto_default_from_env=True, description="tracing plugin"
    )

    WEBSERVER_PROJECTS: ProjectsSettings | None = Field(
        auto_default_from_env=True, description="projects plugin"
    )
    WEBSERVER_RABBITMQ: RabbitSettings | None = Field(
        auto_default_from_env=True, description="rabbitmq plugin"
    )

    # These plugins only require (for the moment) an entry to toggle between enabled/disabled
    WEBSERVER_ANNOUNCEMENTS: bool = False
    WEBSERVER_CLUSTERS: bool = False
    WEBSERVER_DB_LISTENER: bool = True
    WEBSERVER_NOTIFICATIONS: bool = Field(default=True)
    WEBSERVER_GROUPS: bool = True
    WEBSERVER_META_MODELING: bool = True
    WEBSERVER_PRODUCTS: bool = True
    WEBSERVER_PUBLICATIONS: bool = True
    WEBSERVER_REMOTE_DEBUG: bool = True
    WEBSERVER_SOCKETIO: bool = True
    WEBSERVER_TAGS: bool = True
    WEBSERVER_USERS: bool = True
    WEBSERVER_VERSION_CONTROL: bool = True

    #
    WEBSERVER_SECURITY: bool = Field(
        True,
        description="This is a place-holder for future settings."
        "Currently this is a system plugin and cannot be disabled",
    )

    @root_validator()
    @classmethod
    def build_vcs_release_url_if_unset(cls, values):
        vcs_release_url = values.get("SIMCORE_VCS_RELEASE_URL")

        if vcs_release_url is None and (
            vsc_release_tag := values.get("SIMCORE_VCS_RELEASE_TAG")
        ):
            vcs_release_url = f"https://github.com/ITISFoundation/osparc-simcore/releases/tag/{vsc_release_tag}"
            values["SIMCORE_VCS_RELEASE_URL"] = vcs_release_url

        return values

    @validator(
        # List of plugins under-development (keep up-to-date)
        # TODO: consider mark as dev-feature in field extras of Config attr.
        # Then they can be automtically advertised
        "WEBSERVER_META_MODELING",
        "WEBSERVER_VERSION_CONTROL",
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
            _logger.warning(
                "%s still under development and will be disabled.", field.name
            )
        return None if field.allow_none else False

    @cached_property
    def log_level(self) -> int:
        level: int = getattr(logging, self.WEBSERVER_LOGLEVEL.upper())
        return level

    @validator("WEBSERVER_LOGLEVEL")
    @classmethod
    def valid_log_level(cls, value):
        return cls.validate_log_level(value)

    @validator("SC_HEALTHCHECK_TIMEOUT", pre=True)
    @classmethod
    def get_healthcheck_timeout_in_seconds(cls, v):
        # Ex. HEALTHCHECK --interval=5m --timeout=3s
        if isinstance(v, str):
            factor = 1  # defaults on s
            if v.endswith("s"):
                factor = 1
            elif v.endswith("m"):
                factor = 60
            v = v.rstrip("ms")
            return int(v) * factor
        return v

    # HELPERS  --------------------------------------------------------

    def is_enabled(self, field_name: str) -> bool:
        return bool(getattr(self, field_name, None))

    def _get_disabled_public_plugins(self) -> list[str]:
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

    def _export_by_alias(self, **kwargs) -> dict[str, Any]:
        #  This is a small helper to assist export functions since aliases are no longer used by
        #  BaseSettings to define which environment variables to read.
        #  SEE https://github.com/ITISFoundation/osparc-simcore/issues/3372
        #
        # NOTE: This is a copy from pydantic's Config.fields and Config.alias_generator
        # SEE https://pydantic-docs.helpmanual.io/usage/model_config/#options
        # SEE https://pydantic-docs.helpmanual.io/usage/model_config/#alias-generator
        #
        config_fields = {
            "SC_BUILD_DATE": "build_date",
            "SC_VCS_REF": "vcs_ref",
            "SC_VCS_URL": "vcs_url",
            "SIMCORE_VCS_RELEASE_TAG": "vcs_release_tag",
            "SIMCORE_VCS_RELEASE_DATE": "vcs_release_date",
            "SIMCORE_VCS_RELEASE_URL": "vcs_release_url",
            "SWARM_STACK_NAME": "stack_name",
        }
        config_alias_generator = lambda s: s.lower()

        data: dict[str, Any] = self.dict(**kwargs)
        current_keys = list(data.keys())

        for key in current_keys:
            if new_key := (config_fields.get(key) or config_alias_generator(key)):
                data[new_key] = data.pop(key)
        return data

    def public_dict(self) -> dict[str, Any]:
        """Config publicaly available"""

        config = {"invitation_required": False}  # SEE APP_PUBLIC_CONFIG_PER_PRODUCT
        config.update(
            self._export_by_alias(
                include={
                    "API_VERSION",
                    "APP_NAME",
                    "SC_BUILD_DATE",
                    "SC_VCS_REF",
                    "SC_VCS_URL",
                    "SIMCORE_VCS_RELEASE_TAG",
                    "SIMCORE_VCS_RELEASE_DATE",
                    "SIMCORE_VCS_RELEASE_URL",
                },
                exclude_none=True,
            )
        )
        return config

    def to_client_statics(self) -> dict[str, Any]:
        data = self._export_by_alias(
            include={
                "API_VERSION": True,
                "APP_NAME": True,
                "SC_BUILD_DATE": True,
                "SC_VCS_REF": True,
                "SC_VCS_URL": True,
                "SIMCORE_VCS_RELEASE_TAG": True,
                "SIMCORE_VCS_RELEASE_DATE": True,
                "SIMCORE_VCS_RELEASE_URL": True,
                "SWARM_STACK_NAME": True,
                "WEBSERVER_PROJECTS": {"PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES"},
            },
            exclude_none=True,
        )
        data["plugins_disabled"] = self._get_disabled_public_plugins()

        # Alias in addition MUST be camelcase here
        return {snake_to_camel(k): v for k, v in data.items()}


def setup_settings(app: web.Application) -> ApplicationSettings:
    settings: ApplicationSettings = ApplicationSettings.create_from_envs()
    app[APP_SETTINGS_KEY] = settings
    _logger.debug(
        "Captured app settings:\n%s",
        app[APP_SETTINGS_KEY].json(indent=1, sort_keys=True),
    )
    return settings


def get_settings(app: web.Application) -> ApplicationSettings:
    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    assert settings, "Forgot to setup plugin?"  # nosec
    return settings
