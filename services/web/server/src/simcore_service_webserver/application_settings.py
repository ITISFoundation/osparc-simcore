import logging
from functools import cached_property
from typing import Annotated, Any, Final, Literal

from aiohttp import web
from common_library.basic_types import DEFAULT_FACTORY
from common_library.logging.logging_utils_filtering import LoggerName, MessageSubstring
from common_library.pydantic_fields_extension import is_nullable
from models_library.basic_types import LogLevel, PortInt, VersionTag
from models_library.rabbitmq_basic_types import RPCNamespace
from models_library.utils.change_case import snake_to_camel
from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic.fields import Field
from servicelib.logging_utils import LogLevelInt
from settings_library.application import BaseApplicationSettings
from settings_library.email import SMTPSettings
from settings_library.postgres import PostgresSettings
from settings_library.prometheus import PrometheusSettings
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from settings_library.tracing import TracingSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT

from ._meta import API_VERSION, API_VTAG, APP_NAME
from .application_keys import APP_SETTINGS_APPKEY
from .catalog.settings import CatalogSettings
from .collaboration.settings import RealTimeCollaborationSettings
from .diagnostics.settings import DiagnosticsSettings
from .director_v2.settings import DirectorV2Settings
from .dynamic_scheduler.settings import DynamicSchedulerSettings
from .exporter.settings import ExporterSettings
from .fogbugz.settings import FogbugzSettings
from .garbage_collector.settings import GarbageCollectorSettings
from .invitations.settings import InvitationsSettings
from .licenses.settings import LicensesSettings
from .login.settings import LoginSettings
from .long_running_tasks.settings import LongRunningTasksSettings
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
from .trash.settings import TrashSettings
from .users.settings import UsersSettings

_logger = logging.getLogger(__name__)


# NOTE: to mark a plugin as a DEV-FEATURE annotated it with
#    `Field(json_schema_extra={_X_FEATURE_UNDER_DEVELOPMENT: True})`
# This will force it to be disabled when WEBSERVER_DEV_FEATURES_ENABLED=False
_X_FEATURE_UNDER_DEVELOPMENT: Final[str] = "x-dev-feature"


class ApplicationSettings(BaseApplicationSettings, MixinLoggingSettings):
    # CODE STATICS ---------------------------------------------------------
    API_VERSION: str = API_VERSION
    APP_NAME: str = APP_NAME
    API_VTAG: VersionTag = TypeAdapter(VersionTag).validate_python(API_VTAG)

    # RUNTIME  -----------------------------------------------------------
    # settings defined from environs defined when container runs
    #
    # NOTE: Please keep fields alphabetically if possible
    AIODEBUG_SLOW_DURATION_SECS: float = 0

    # Release information: Passed by the osparc-ops-autodeployer
    SIMCORE_VCS_RELEASE_TAG: Annotated[
        str | None,
        Field(
            description="Name of the tag that marks this release, or None if undefined",
            examples=["ResistanceIsFutile10"],
        ),
    ] = None

    SIMCORE_VCS_RELEASE_URL: Annotated[
        AnyHttpUrl | None,
        Field(
            description="URL to release notes",
            examples=[
                "https://github.com/ITISFoundation/osparc-simcore/releases/tag/staging_ResistanceIsFutile10"
            ],
        ),
    ] = None

    SWARM_STACK_NAME: Annotated[
        str | None,
        Field(None, description="Stack name defined upon deploy (see main Makefile)"),
    ]

    WEBSERVER_APP_FACTORY_NAME: Annotated[
        Literal["WEBSERVER_FULL_APP_FACTORY", "WEBSERVER_AUTHZ_APP_FACTORY"],
        Field(
            description="Application factory to be lauched by the gunicorn server",
        ),
    ] = "WEBSERVER_FULL_APP_FACTORY"

    WEBSERVER_DEV_FEATURES_ENABLED: Annotated[
        bool,
        Field(
            description="Enables development features. WARNING: make sure it is disabled in production .env file!",
        ),
    ] = False
    WEBSERVER_CREDIT_COMPUTATION_ENABLED: Annotated[
        bool, Field(description="Enables credit computation features.")
    ] = False

    WEBSERVER_FUNCTIONS: Annotated[
        bool,
        Field(
            description="Metamodeling functions plugin",
        ),
    ] = False

    WEBSERVER_LOGLEVEL: Annotated[
        LogLevel,
        Field(
            validation_alias=AliasChoices(
                "WEBSERVER_LOGLEVEL", "LOG_LEVEL", "LOGLEVEL"
            ),
            # NOTE: suffix '_LOGLEVEL' is used overall
        ),
    ] = LogLevel.WARNING

    WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED: Annotated[
        bool,
        Field(
            validation_alias=AliasChoices(
                "WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"
            ),
            description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
        ),
    ] = False

    WEBSERVER_LOG_FILTER_MAPPING: Annotated[
        dict[LoggerName, list[MessageSubstring]],
        Field(
            default_factory=dict,
            validation_alias=AliasChoices(
                "WEBSERVER_LOG_FILTER_MAPPING", "LOG_FILTER_MAPPING"
            ),
            description="is a dictionary that maps specific loggers (such as 'uvicorn.access' or 'gunicorn.access') to a list of log message patterns that should be filtered out.",
        ),
    ] = DEFAULT_FACTORY

    WEBSERVER_RPC_NAMESPACE: Annotated[
        RPCNamespace | None,
        Field(description="Namespace for the RPC service, if any, otherwise None"),
    ]

    WEBSERVER_SERVER_HOST: Annotated[
        # TODO: find a better name!?
        str,
        Field(
            description="host name to serve within the container."
            "NOTE that this different from WEBSERVER_HOST env which is the host seen outside the container",
        ),
    ] = "0.0.0.0"  # nosec

    WEBSERVER_HOST: Annotated[
        str | None,
        Field(
            None, validation_alias=AliasChoices("WEBSERVER_HOST", "HOST", "HOSTNAME")
        ),
    ]

    WEBSERVER_PORT: PortInt = TypeAdapter(PortInt).validate_python(DEFAULT_AIOHTTP_PORT)

    WEBSERVER_FRONTEND: Annotated[
        FrontEndAppSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="front-end static settings",
        ),
    ]

    # PLUGINS ----------------

    WEBSERVER_ACTIVITY: Annotated[
        PrometheusSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="activity plugin",
        ),
    ]
    WEBSERVER_CATALOG: Annotated[
        CatalogSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="catalog service client's plugin",
        ),
    ]
    WEBSERVER_DB: Annotated[
        PostgresSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="database plugin",
        ),
    ]
    WEBSERVER_DIAGNOSTICS: Annotated[
        DiagnosticsSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="diagnostics plugin",
        ),
    ]
    WEBSERVER_DIRECTOR_V2: Annotated[
        DirectorV2Settings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="director-v2 service client's plugin",
        ),
    ]

    WEBSERVER_DYNAMIC_SCHEDULER: Annotated[
        DynamicSchedulerSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_EMAIL: Annotated[
        SMTPSettings | None, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    WEBSERVER_EXPORTER: Annotated[
        ExporterSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="exporter plugin",
        ),
    ]

    WEBSERVER_FOGBUGZ: Annotated[
        FogbugzSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_GARBAGE_COLLECTOR: Annotated[
        GarbageCollectorSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="garbage collector plugin",
        ),
    ]

    WEBSERVER_INVITATIONS: Annotated[
        InvitationsSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="invitations plugin",
        ),
    ]

    WEBSERVER_LICENSES: Annotated[
        LicensesSettings | None | bool,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            # NOTE: `bool` is to keep backwards compatibility
        ),
    ]

    WEBSERVER_LOGIN: Annotated[
        LoginSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="login plugin",
        ),
    ]

    WEBSERVER_LONG_RUNNING_TASKS: Annotated[
        LongRunningTasksSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="long running tasks plugin",
        ),
    ]

    WEBSERVER_PAYMENTS: Annotated[
        PaymentsSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="payments plugin settings",
        ),
    ]

    WEBSERVER_PROJECTS: Annotated[
        ProjectsSettings | None,
        Field(json_schema_extra={"auto_default_from_env": True}),
    ]

    WEBSERVER_REALTIME_COLLABORATION: Annotated[
        RealTimeCollaborationSettings | None,
        Field(
            description="Enables real-time collaboration features",
            json_schema_extra={
                "auto_default_from_env": True,
            },
        ),
    ]

    WEBSERVER_REDIS: Annotated[
        RedisSettings | None, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    WEBSERVER_REST: Annotated[
        RestSettings | None,
        Field(
            description="rest api plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_RESOURCE_MANAGER: Annotated[
        ResourceManagerSettings,
        Field(
            description="resource_manager plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]
    WEBSERVER_RESOURCE_USAGE_TRACKER: Annotated[
        ResourceUsageTrackerSettings | None,
        Field(
            description="resource usage tracker service client's plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]
    WEBSERVER_SCICRUNCH: Annotated[
        SciCrunchSettings | None,
        Field(
            description="scicrunch plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]
    WEBSERVER_SESSION: Annotated[
        SessionSettings,
        Field(
            description="session plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_STATICWEB: Annotated[
        StaticWebserverModuleSettings | None,
        Field(
            description="static-webserver service plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_STORAGE: Annotated[
        StorageSettings | None,
        Field(
            description="storage service client's plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_STUDIES_DISPATCHER: Annotated[
        StudiesDispatcherSettings | None,
        Field(
            description="studies dispatcher plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_TRACING: Annotated[
        TracingSettings | None,
        Field(
            description="tracing plugin",
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_TRASH: Annotated[
        TrashSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    WEBSERVER_RABBITMQ: Annotated[
        RabbitSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    WEBSERVER_USERS: Annotated[
        UsersSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
        ),
    ]

    # These plugins only require (for the moment) an entry to toggle between enabled/disabled
    WEBSERVER_ANNOUNCEMENTS: bool = False
    WEBSERVER_API_KEYS: bool = True
    WEBSERVER_DB_LISTENER: bool = True
    WEBSERVER_FOLDERS: bool = True
    WEBSERVER_GROUPS: bool = True
    WEBSERVER_NOTIFICATIONS: bool = True
    WEBSERVER_PRODUCTS: bool = True
    WEBSERVER_PROFILING: bool = False
    WEBSERVER_PUBLICATIONS: bool = True
    WEBSERVER_REMOTE_DEBUG: bool = True
    WEBSERVER_SOCKETIO: bool = True
    WEBSERVER_TAGS: bool = True
    WEBSERVER_WALLETS: bool = True
    WEBSERVER_WORKSPACES: bool = True
    WEBSERVER_CONVERSATIONS: bool = True

    WEBSERVER_SECURITY: Annotated[
        bool,
        Field(
            description="This is a place-holder for future settings."
            "Currently this is a system plugin and cannot be disabled",
        ),
    ] = True

    @model_validator(mode="before")
    @classmethod
    def _build_vcs_release_url_if_unset(cls, values):
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

    @model_validator(mode="before")
    @classmethod
    def _disable_features_under_development_in_production(cls, data: Any) -> Any:
        """Force disables plugins marked '_X_FEATURE_UNDER_DEVELOPMENT' when WEBSERVER_DEV_FEATURES_ENABLED=False"""

        dev_features_allowed = TypeAdapter(bool).validate_python(
            data.get("WEBSERVER_DEV_FEATURES_ENABLED", False)
        )

        if dev_features_allowed:
            return data

        for field_name, field in cls.model_fields.items():
            json_schema = field.json_schema_extra or {}
            if callable(field.json_schema_extra):
                json_schema = {}
                field.json_schema_extra(json_schema)

            assert isinstance(json_schema, dict)  # nosec
            if json_schema.get(_X_FEATURE_UNDER_DEVELOPMENT):
                assert not dev_features_allowed  # nosec
                _logger.warning(
                    "'%s' is still under development and will be forcibly disabled [WEBSERVER_DEV_FEATURES_ENABLED=%s].",
                    field_name,
                    dev_features_allowed,
                )
                data[field_name] = None if is_nullable(field) else False

        return data

    @field_validator("WEBSERVER_LOGLEVEL")
    @classmethod
    def _valid_log_level(cls, value):
        return cls.validate_log_level(value)

    @field_validator("SC_HEALTHCHECK_TIMEOUT", mode="before")
    @classmethod
    def _get_healthcheck_timeout_in_seconds(cls, v):
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

    @cached_property
    def log_level(self) -> LogLevelInt:
        level: LogLevelInt = getattr(logging, self.WEBSERVER_LOGLEVEL.upper())
        return level

    def is_enabled(self, field_name: str) -> bool:
        return bool(getattr(self, field_name, None))

    def _get_disabled_advertised_plugins(self) -> list[str]:
        """List of plugins that are disabled to be advertised to the client"""
        # NOTE: this list is limited for security reasons. An unbounded list
        # might reveal critical info on the settings of a deploy to the client.
        # SEE https://github.com/ITISFoundation/osparc-simcore/issues/7688
        advertised_plugins: Final = {
            "WEBSERVER_EXPORTER",
            "WEBSERVER_FOLDERS",
            "WEBSERVER_FUNCTIONS",
            "WEBSERVER_LICENSES",
            "WEBSERVER_PAYMENTS",
            "WEBSERVER_SCICRUNCH",
            "WEBSERVER_REALTIME_COLLABORATION",
        }
        return [_ for _ in advertised_plugins if not self.is_enabled(_)] + [
            # NOTE: Permanently retired in https://github.com/ITISFoundation/osparc-simcore/pull/7182
            # Kept here to disable front-end
            "WEBSERVER_META_MODELING",
            "WEBSERVER_VERSION_CONTROL",
        ]

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

        data: dict[str, Any] = self.model_dump(**kwargs)
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
                "WEBSERVER_DEV_FEATURES_ENABLED": True,
                "WEBSERVER_LOGIN": {
                    "LOGIN_ACCOUNT_DELETION_RETENTION_DAYS",
                    "LOGIN_2FA_REQUIRED",
                },
                "WEBSERVER_PROJECTS": {
                    "PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES",
                },
                "WEBSERVER_REALTIME_COLLABORATION": {
                    "RTC_MAX_NUMBER_OF_USERS",
                },
                "WEBSERVER_SESSION": {"SESSION_COOKIE_MAX_AGE"},
                "WEBSERVER_TRASH": {
                    "TRASH_RETENTION_DAYS",
                },
                "WEBSERVER_LONG_RUNNING_TASKS": {
                    "LONG_RUNNING_TASKS_NAMESPACE_SUFFIX",
                },
            },
            exclude_none=True,
        )
        data["plugins_disabled"] = self._get_disabled_advertised_plugins()

        # Alias in addition MUST be camelcase here
        return {snake_to_camel(k): v for k, v in data.items()}


def setup_settings(app: web.Application) -> ApplicationSettings:
    settings: ApplicationSettings = ApplicationSettings.create_from_envs()
    app[APP_SETTINGS_APPKEY] = settings
    _logger.debug(
        "Captured app settings:\n%s",
        lambda: settings.model_dump_json(indent=1),
    )
    return settings


def get_application_settings(app: web.Application) -> ApplicationSettings:
    settings: ApplicationSettings = app[APP_SETTINGS_APPKEY]
    assert settings, "Forgot to setup plugin?"  # nosec
    return settings
