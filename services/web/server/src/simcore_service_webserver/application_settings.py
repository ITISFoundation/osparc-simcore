import logging
from functools import cached_property
from typing import Annotated, Any, Final

from aiohttp import web
from common_library.basic_types import DEFAULT_FACTORY
from common_library.pydantic_fields_extension import is_nullable
from models_library.basic_types import LogLevel, PortInt, VersionTag
from models_library.utils.change_case import snake_to_camel
from pydantic import (
    AliasChoices,
    AnyHttpUrl,
    TypeAdapter,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic.fields import Field
from servicelib.logging_utils_filtering import LoggerName, MessageSubstring
from settings_library.application import BaseApplicationSettings
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
from .trash.settings import TrashSettings
from .users.settings import UsersSettings

_logger = logging.getLogger(__name__)


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
            default=None,
            description="Name of the tag that marks this release, or None if undefined",
            examples=["ResistanceIsFutile10"],
        ),
    ]

    SIMCORE_VCS_RELEASE_URL: Annotated[
        AnyHttpUrl | None,
        Field(
            default=None,
            description="URL to release notes",
            examples=[
                "https://github.com/ITISFoundation/osparc-simcore/releases/tag/staging_ResistanceIsFutile10"
            ],
        ),
    ]

    SWARM_STACK_NAME: Annotated[
        str | None,
        Field(None, description="Stack name defined upon deploy (see main Makefile)"),
    ]

    WEBSERVER_DEV_FEATURES_ENABLED: Annotated[
        bool,
        Field(
            default=False,
            description="Enables development features. WARNING: make sure it is disabled in production .env file!",
        ),
    ]
    WEBSERVER_CREDIT_COMPUTATION_ENABLED: Annotated[
        bool, Field(default=False, description="Enables credit computation features.")
    ]

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
            default=False,
            validation_alias=AliasChoices(
                "WEBSERVER_LOG_FORMAT_LOCAL_DEV_ENABLED", "LOG_FORMAT_LOCAL_DEV_ENABLED"
            ),
            description="Enables local development log format. WARNING: make sure it is disabled if you want to have structured logs!",
        ),
    ]

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

    WEBSERVER_LOGIN: Annotated[
        LoginSettings | None,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="login plugin",
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
    WEBSERVER_LICENSES: bool = False
    WEBSERVER_META_MODELING: bool = True
    WEBSERVER_NOTIFICATIONS: bool = True
    WEBSERVER_PRODUCTS: bool = True
    WEBSERVER_PROFILING: bool = False
    WEBSERVER_PUBLICATIONS: bool = True
    WEBSERVER_REMOTE_DEBUG: bool = True
    WEBSERVER_SOCKETIO: bool = True
    WEBSERVER_TAGS: bool = True
    WEBSERVER_VERSION_CONTROL: bool = True
    WEBSERVER_WALLETS: bool = True
    WEBSERVER_WORKSPACES: bool = True

    WEBSERVER_SECURITY: Annotated[
        bool,
        Field(
            default=True,
            description="This is a place-holder for future settings."
            "Currently this is a system plugin and cannot be disabled",
        ),
    ]

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

    @field_validator(
        # List of plugins under-development (keep up-to-date)
        # TODO: consider mark as dev-feature in field extras of Config attr.
        # Then they can be automtically advertised
        "WEBSERVER_META_MODELING",
        "WEBSERVER_VERSION_CONTROL",
        mode="before",
    )
    @classmethod
    def _enable_only_if_dev_features_allowed(cls, v, info: ValidationInfo):
        """Ensures that plugins 'under development' get programatically
        disabled if WEBSERVER_DEV_FEATURES_ENABLED=False
        """
        if info.data["WEBSERVER_DEV_FEATURES_ENABLED"]:
            return v
        if v:
            _logger.warning(
                "%s still under development and will be disabled.", info.field_name
            )

        return (
            None
            if info.field_name and is_nullable(cls.model_fields[info.field_name])
            else False
        )

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
    def log_level(self) -> int:
        level: int = getattr(logging, self.WEBSERVER_LOGLEVEL.upper())
        return level

    def is_enabled(self, field_name: str) -> bool:
        return bool(getattr(self, field_name, None))

    def _get_disabled_public_plugins(self) -> list[str]:
        # NOTE: this list is limited for security reasons. An unbounded list
        # might reveal critical info on the settings of a deploy to the client.
        # TODO: more reliable definition of a "plugin" and whether it can be advertised or not
        # (extra var? e.g. Field( ... , x_advertise_plugin=True))
        public_plugin_candidates: Final = {
            "WEBSERVER_EXPORTER",
            "WEBSERVER_FOLDERS",
            "WEBSERVER_LICENSES",
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
                "WEBSERVER_LICENSES": True,
                "WEBSERVER_LOGIN": {
                    "LOGIN_ACCOUNT_DELETION_RETENTION_DAYS",
                    "LOGIN_2FA_REQUIRED",
                },
                "WEBSERVER_PROJECTS": {
                    "PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES",
                },
                "WEBSERVER_TRASH": {
                    "TRASH_RETENTION_DAYS",
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
        app[APP_SETTINGS_KEY].model_dump_json(indent=1, warnings="none"),
    )
    return settings


def get_application_settings(app: web.Application) -> ApplicationSettings:
    settings: ApplicationSettings = app[APP_SETTINGS_KEY]
    assert settings, "Forgot to setup plugin?"  # nosec
    return settings
