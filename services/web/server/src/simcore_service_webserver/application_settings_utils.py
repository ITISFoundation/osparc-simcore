# NOTE: Conversion helpers like 'convert_to_app_config' and 'convert_to_environ_vars' allows us
# to fall back to an equivalent config or environs provided some settings.
#
# This allows to keep many of the logic layers based on a given config whose
# refactoring would report very little. E.g. many test fixtures were based on given configs
#

import functools
import logging
from typing import Any

from aiohttp import web
from common_library.pydantic_fields_extension import get_type, is_nullable
from pydantic.types import SecretStr
from servicelib.aiohttp.typing_extension import Handler

from ._constants import MSG_UNDER_DEVELOPMENT
from .application_settings import ApplicationSettings, get_application_settings

_logger = logging.getLogger(__name__)


def convert_to_app_config(app_settings: ApplicationSettings) -> dict[str, Any]:
    """Maps current ApplicationSettings object into former trafaret-based config"""

    return {
        "version": "1.0",
        "main": {
            "host": app_settings.WEBSERVER_SERVER_HOST,
            "port": app_settings.WEBSERVER_PORT,
            "log_level": f"{app_settings.WEBSERVER_LOGLEVEL}",
            "testing": False,  # TODO: deprecate!
            "studies_access_enabled": (
                int(
                    app_settings.WEBSERVER_STUDIES_DISPATCHER.STUDIES_ACCESS_ANONYMOUS_ALLOWED
                )
                if app_settings.WEBSERVER_STUDIES_DISPATCHER
                else 0
            ),
        },
        "tracing": {
            "enabled": 1 if app_settings.WEBSERVER_TRACING is not None else 0,
        },
        "socketio": {"enabled": app_settings.WEBSERVER_SOCKETIO},
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
                app_settings.WEBSERVER_GARBAGE_COLLECTOR,
                "GARBAGE_COLLECTOR_INTERVAL_S",
                None,
            ),
            "redis": {
                "enabled": app_settings.WEBSERVER_REDIS is not None,
                "host": getattr(app_settings.WEBSERVER_REDIS, "REDIS_HOST", None),
                "port": getattr(app_settings.WEBSERVER_REDIS, "REDIS_PORT", None),
                "password": getattr(
                    app_settings.WEBSERVER_REDIS, "REDIS_PASSWORD", None
                ),
            },
        },
        # added to support legacy ----
        "garbage_collector": {
            "enabled": app_settings.WEBSERVER_GARBAGE_COLLECTOR is not None
        },
        "redis": {"enabled": app_settings.WEBSERVER_REDIS is not None},
        # -----------------------------
        "login": {
            "enabled": app_settings.WEBSERVER_LOGIN is not None,
            "registration_invitation_required": (
                1
                if getattr(
                    app_settings.WEBSERVER_LOGIN,
                    "LOGIN_REGISTRATION_INVITATION_REQUIRED",
                    None,
                )
                else 0
            ),
            "registration_confirmation_required": (
                1
                if getattr(
                    app_settings.WEBSERVER_LOGIN,
                    "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED",
                    None,
                )
                else 0
            ),
            "password_min_length": (
                12
                if getattr(
                    app_settings.WEBSERVER_LOGIN, "LOGIN_PASSWORD_MIN_LENGTH", None
                )
                else 0
            ),
        },
        "smtp": {
            "host": getattr(app_settings.WEBSERVER_EMAIL, "SMTP_HOST", None),
            "port": getattr(app_settings.WEBSERVER_EMAIL, "SMTP_PORT", None),
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
        "rest": {
            "version": app_settings.API_VTAG,
            "enabled": app_settings.WEBSERVER_REST is not None,
        },
        "projects": {"enabled": app_settings.WEBSERVER_PROJECTS},
        "session": {
            "secret_key": app_settings.WEBSERVER_SESSION.SESSION_SECRET_KEY.get_secret_value()
        },
        "activity": {
            "enabled": app_settings.WEBSERVER_ACTIVITY is not None,
            "prometheus_url": getattr(
                app_settings.WEBSERVER_ACTIVITY, "PROMETHEUS_URL", None
            ),
            "prometheus_api_version": getattr(
                app_settings.WEBSERVER_ACTIVITY, "PROMETHEUS_VTAG", None
            ),
        },
        "clusters": {"enabled": app_settings.WEBSERVER_CLUSTERS},
        "computation": {"enabled": app_settings.is_enabled("WEBSERVER_NOTIFICATIONS")},
        "diagnostics": {"enabled": app_settings.is_enabled("WEBSERVER_DIAGNOSTICS")},
        "director-v2": {"enabled": app_settings.is_enabled("WEBSERVER_DIRECTOR_V2")},
        "exporter": {"enabled": app_settings.WEBSERVER_EXPORTER is not None},
        "groups": {"enabled": app_settings.WEBSERVER_GROUPS},
        "meta_modeling": {"enabled": app_settings.WEBSERVER_META_MODELING},
        "products": {"enabled": app_settings.WEBSERVER_PRODUCTS},
        "publications": {"enabled": app_settings.WEBSERVER_PUBLICATIONS},
        "remote_debug": {"enabled": app_settings.WEBSERVER_REMOTE_DEBUG},
        "security": {"enabled": True},
        "scicrunch": {"enabled": app_settings.WEBSERVER_SCICRUNCH is not None},
        "statics": {
            "enabled": app_settings.WEBSERVER_FRONTEND is not None
            and app_settings.WEBSERVER_STATICWEB is not None
        },
        # NOTE  app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED did not apply
        "studies_dispatcher": {
            "enabled": app_settings.WEBSERVER_STUDIES_DISPATCHER is not None
        },
        "tags": {"enabled": app_settings.WEBSERVER_TAGS},
        "users": {"enabled": app_settings.WEBSERVER_USERS is not None},
        "version_control": {"enabled": app_settings.WEBSERVER_VERSION_CONTROL},
        "wallets": {"enabled": app_settings.WEBSERVER_WALLETS},
        "folders": {"enabled": app_settings.WEBSERVER_FOLDERS},
        "workspaces": {"enabled": app_settings.WEBSERVER_WORKSPACES},
    }


def convert_to_environ_vars(  # noqa: C901, PLR0915, PLR0912
    cfg: dict[str, Any]
) -> dict[str, Any]:
    """Creates envs dict out of config dict

    NOTE: ONLY used to support legacy introduced by traferet vs settings_library.
    """
    # pylint:disable=too-many-branches
    # pylint:disable=too-many-statements

    envs = {}

    def _set_if_disabled(field_name, section):
        # Assumes that by default is enabled
        enabled = section.get("enabled", True)
        field = ApplicationSettings.model_fields[field_name]
        if not enabled:
            envs[field_name] = "null" if is_nullable(field) else "0"
        elif get_type(field) == bool:
            envs[field_name] = "1"

    if main := cfg.get("main"):
        envs["WEBSERVER_PORT"] = main.get("port")
        envs["WEBSERVER_LOGLEVEL"] = main.get("log_level")
        envs["WEBSERVER_STUDIES_ACCESS_ENABLED"] = main.get("studies_access_enabled")

    if section := cfg.get("tracing"):
        _set_if_disabled("WEBSERVER_TRACING", section)

    if db := cfg.get("db"):
        if section := db.get("postgres"):
            envs["POSTGRES_DB"] = section.get("database")
            envs["POSTGRES_HOST"] = section.get("host")
            envs["POSTGRES_MAXSIZE"] = section.get("maxsize")
            envs["POSTGRES_MINSIZE"] = section.get("minsize")
            envs["POSTGRES_PASSWORD"] = section.get("password")
            envs["POSTGRES_PORT"] = section.get("port")
            envs["POSTGRES_USER"] = section.get("user")

        _set_if_disabled("WEBSERVER_DB", db)

    if section := cfg.get("rabbitmq"):
        envs["RABBIT_HOST"] = section.get("host")
        envs["RABBIT_PORT"] = section.get("port")
        envs["RABBIT_USER"] = section.get("user")
        envs["RABBIT_PASSWORD"] = section.get("password")
        envs["RABBIT_SECURE"] = section.get("secure")

    if section := cfg.get("resource_manager"):
        _set_if_disabled("WEBSERVER_RESOURCE_MANAGER", section)

        envs["RESOURCE_MANAGER_RESOURCE_TTL_S"] = section.get(
            "resource_deletion_timeout_seconds"
        )
        envs["GARBAGE_COLLECTOR_INTERVAL_S"] = section.get(
            "garbage_collection_interval_seconds"
        )

        if section2 := section.get("redis"):
            _set_if_disabled("WEBSERVER_REDIS", section2)
            envs["REDIS_HOST"] = section2.get("host")
            envs["REDIS_PORT"] = section2.get("port")
            envs["REDIS_PASSWORD"] = section2.get("password")

    if section := cfg.get("garbage_collector"):
        _set_if_disabled("WEBSERVER_GARBAGE_COLLECTOR", section)

    if section := cfg.get("login"):
        _set_if_disabled("WEBSERVER_LOGIN", section)

        envs["LOGIN_REGISTRATION_INVITATION_REQUIRED"] = section.get(
            "registration_invitation_required"
        )
        envs["LOGIN_REGISTRATION_CONFIRMATION_REQUIRED"] = section.get(
            "registration_confirmation_required"
        )

    if section := cfg.get("smtp"):
        envs["SMTP_HOST"] = section.get("host")
        envs["SMTP_PORT"] = section.get("port")
        envs["SMTP_USERNAME"] = section.get("username")
        envs["SMTP_PASSWORD"] = section.get("password")

    if section := cfg.get("storage"):
        _set_if_disabled("WEBSERVER_STORAGE", section)

        envs["STORAGE_HOST"] = section.get("host")
        envs["STORAGE_PORT"] = section.get("port")
        envs["STORAGE_VTAG"] = section.get("version")

    if section := cfg.get("catalog"):
        _set_if_disabled("WEBSERVER_CATALOG", section)

        envs["CATALOG_HOST"] = section.get("host")
        envs["CATALOG_PORT"] = section.get("port")
        envs["CATALOG_VTAG"] = section.get("version")

    if section := cfg.get("session"):
        envs["SESSION_SECRET_KEY"] = section.get("secret_key")

    if section := cfg.get("activity"):
        _set_if_disabled("WEBSERVER_ACTIVITY", section)
        envs["PROMETHEUS_URL"] = section.get("prometheus_url")
        envs["PROMETHEUS_USERNAME"] = section.get("prometheus_username")
        envs["PROMETHEUS_PASSWORD"] = section.get("prometheus_password")
        envs["PROMETHEUS_VTAG"] = section.get("prometheus_api_version")

    if section := cfg.get("computation"):
        _set_if_disabled("WEBSERVER_NOTIFICATIONS", section)

    if section := cfg.get("diagnostics"):
        _set_if_disabled("WEBSERVER_DIAGNOSTICS", section)

    if section := cfg.get("director-v2"):
        _set_if_disabled("WEBSERVER_DIRECTOR_V2", section)

    if section := cfg.get("exporter"):
        _set_if_disabled("WEBSERVER_EXPORTER", section)

    if section := cfg.get("statics"):
        _set_if_disabled("WEBSERVER_FRONTEND", section)
        _set_if_disabled("WEBSERVER_STATICWEB", section)

    for settings_name in (
        "WEBSERVER_CLUSTERS",
        "WEBSERVER_GARBAGE_COLLECTOR",
        "WEBSERVER_GROUPS",
        "WEBSERVER_META_MODELING",
        "WEBSERVER_PRODUCTS",
        "WEBSERVER_PROJECTS",
        "WEBSERVER_PUBLICATIONS",
        "WEBSERVER_REMOTE_DEBUG",
        "WEBSERVER_REST",
        "WEBSERVER_SOCKETIO",
        "WEBSERVER_STUDIES_ACCESS",
        "WEBSERVER_STUDIES_DISPATCHER",
        "WEBSERVER_TAGS",
        "WEBSERVER_USERS",
        "WEBSERVER_VERSION_CONTROL",
        "WEBSERVER_WALLETS",
        "WEBSERVER_FOLDERS",
    ):
        section_name = settings_name.replace("WEBSERVER_", "").lower()
        if section := cfg.get(section_name):
            _set_if_disabled(settings_name, section)

    # NOTE: The final envs list prunes all env vars set to None
    return {k: v for k, v in envs.items() if v is not None}


#
# decorators
#


def requires_dev_feature_enabled(handler: Handler):
    @functools.wraps(handler)
    async def _handler_under_dev(request: web.Request):
        app_settings = get_application_settings(request.app)
        if not app_settings.WEBSERVER_DEV_FEATURES_ENABLED:
            raise NotImplementedError(MSG_UNDER_DEVELOPMENT)
        return await handler(request)

    return _handler_under_dev
