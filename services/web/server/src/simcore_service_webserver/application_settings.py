import logging
from functools import cached_property
from typing import Any, Final

from aiohttp import web
from models_library.basic_types import (
    BootModeEnum,
    BuildTargetEnum,
    LogLevel,
    PortInt,
    VersionTag,
)
from models_library.utils.change_case import snake_to_camel
from pydantic import AnyHttpUrl, parse_obj_as, root_validator, validator
from pydantic.fields import Field, ModelField
from pydantic.types import PositiveInt
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
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
from .dynamic_scheduler.settings import DynamicSchedulerSettings
from .exporter.settings import ExporterSettings
from .garbage_collector.settings import GarbageCollectorSettings
from .invitations.settings import InvitationsSettings
from .login.settings import LoginSettings
from .payments.settings import PaymentsSettings
from .projects.settings import ProjectsSettings
from .resource_manager.settings import ResourceManagerSettings
from .resource_usage.settings import ResourceUsageTrackerSettings
from .rest.settings import RestSettings
from .scicrunch.settings import SciCrunchSettings
from .session.settings import SessionSettings
from .statics.settings import FrontEndAppSettings, StaticWebserverModuleSettings
from .storage.settings import StorageSettings
from .studies_dispatcher.settings import StudiesDispatcherSettings
from .users.settings import UsersSettings

_logger = logging.getLogger(__name__)


class ApplicationSettings(BaseCustomSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = parse_obj_as(VersionTag, API_VTAG)

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
        description="Name of the tag that marks this release, or None if undefined",
        example="ResistanceIsFutile10",
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
        default=False,
        description="Enables development features. WARNING: make sure it is disabled in production .env file!",
    )
    WEBSERVER_CREDIT_COMPUTATION_ENABLED: bool = Field(
        default=False, description="Enables credit computation features."
    )
    WEBSERVER_LOGLEVEL: LogLevel = Field(
        default=LogLevel.WARNING.value,
        env=["WEBSERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"],
        # NOTE: suffix '_LOGLEVEL' is used overall
    )

    WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED: bool = Field(
        default=False,
        env=["WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"],
        description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
    )
    WEBSERVER_LOG_FILTER_MAPPING: dict[LoggerName, list[MessageSubstring]] = Field(
        default_factory=dict,
        env=["WEBSERVER_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"],
        description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
    )
    # TODO: find a better name!?
    WEBSERVER_SERVER_HOST: str = Field(
        default="0.0.0.0",  # nosec
        description="host name to serve within the container."
        "NOTE that this different from WEBSERVER_HOST env which is the host seen outside the container",
    )
    WEBSERVER_HOST: str | None = Field(None, env=["WEBSERVER_HOST", "HOST", "HOSTNAME"])
    WEBSERVER_PORT: PortInt = parse_obj_as(PortInt, DEFAULT_AIOHTTP_PORT)

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

    WEBSERVER_PAYMENTS: PaymentsSettings | None = Field(
        auto_default_from_env=True, description="payments plugin settings"
    )

    WEBSERVER_DYNAMIC_SCHEDULER: DynamicSchedulerSettings | None = Field(
        auto_default_from_env=True, description="dynamic-scheduler plugin settings"
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
    WEBSERVER_USERS: UsersSettings | None = Field(
        auto_default_from_env=True, description="users plugin"
    )

    # These plugins only require (for the moment) an entry to toggle between enabled/disabled
    WEBSERVER_ANNOUNCEMENTS: bool = False
    WEBSERVER_API_KEYS: bool = True
    WEBSERVER_CLUSTERS: bool = False
    WEBSERVER_DB_LISTENER: bool = True
    WEBSERVER_FOLDERS: bool = True
    WEBSERVER_WORKSPACES: bool = True
    WEBSERVER_GROUPS: bool = True
    WEBSERVER_META_MODELING: bool = True
    WEBSERVER_NOTIFICATIONS: bool = Field(default=True)
    WEBSERVER_PRODUCTS: bool = True
    WEBSERVER_PUBLICATIONS: bool = True
    WEBSERVER_REMOTE_DEBUG: bool = True
    WEBSERVER_SOCKETIO: bool = True
    WEBSERVER_TAGS: bool = True
    WEBSERVER_VERSION_CONTROL: bool = True
    WEBSERVER_WALLETS: bool = True
    WEBSERVER_PROFILING: bool = False

    #
    WEBSERVER_SECURITY: bool = Field(
        default=True,
        description="This is a place-holder for future settings."
        "Currently this is a system plugin and cannot be disabled",
    )

    @root_validator()
    @classmethod
    def build_vcs_release_url_if_unset(cls, values):
        release_url = values.get("SIMCORE_VCS_RELEASE_URL")

        if release_url is None and (
            vsc_release_tag := values.get("SIMCORE_VCS_RELEASE_TAG")
        ):
            if vsc_release_tag == "latest":
                release_url = (
                    "https://github.com/ITISFoundation/osparc-simcore/commits/master/"
                )
            else:
                release_url = f"https://github.com/ITISFoundation/osparc-simcore/releases/tag/{vsc_release_tag}"
            values["SIMCORE_VCS_RELEASE_URL"] = release_url

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

    @validator("WEBSERVER_LOGLEVEL", pre=True)
    @classmethod
    def valid_log_level(cls, value: str) -> str:
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
        # NOTE: this list is limited for security reasons. An unbounded list
        # might reveal critical info on the settings of a deploy to the client.
        # TODO: more reliable definition of a "plugin" and whether it can be advertised or not
        # (extra var? e.g. Field( ... , x_advertise_plugin=True))
        public_plugin_candidates: Final = {
            "WEBSERVER_CLUSTERS",
            "WEBSERVER_EXPORTER",
            "WEBSERVER_FOLDERS",
            "WEBSERVER_META_MODELING",
            "WEBSERVER_PAYMENTS",
            "WEBSERVER_SCICRUNCH",
            "WEBSERVER_VERSION_CONTROL",
        }
        return [_ for _ in public_plugin_candidates if not self.is_enabled(_)]

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
            "SIMCORE_VCS_RELEASE_URL": "vcs_release_url",
            "SWARM_STACK_NAME": "stack_name",
        }

        def config_alias_generator(s):
            return s.lower()

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
                "SIMCORE_VCS_RELEASE_URL": True,
                "SWARM_STACK_NAME": True,
                "WEBSERVER_PROJECTS": {
                    "PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES",
                    "PROJECTS_TRASH_RETENTION_DAYS",
                },
                "WEBSERVER_LOGIN": {
                    "LOGIN_ACCOUNT_DELETION_RETENTION_DAYS",
                    "LOGIN_2FA_REQUIRED",
                },
                "WEBSERVER_SESSION": {"SESSION_COOKIE_MAX_AGE"},
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


def get_application_settings(app: web.Application) -> ApplicationSettings:
    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    assert settings, "Forgot to setup plugin?"  # nosec
    return settings
