import logging
from typing import Any, Dict

from pydantic.types import SecretStr

from .application_settings import ApplicationSettings

log = logging.getLogger(__name__)


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
        "socketio": {"enabled": app_settings.WEBSERVER_SOCKETIO},
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
        "redis": {
            "enabled": app_settings.WEBSERVER_REDIS is not None
        },  # added to support legacy
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
        "rest": {
            "version": app_settings.API_VTAG,
            "enabled": app_settings.WEBSERVER_REST,
        },
        "projects": {"enabled": app_settings.WEBSERVER_PROJECTS},
        "session": {
            "secret_key": app_settings.WEBSERVER_SESSION.SESSION_SECRET_KEY.get_secret_value()
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
        "clusters": {"enabled": app_settings.WEBSERVER_CLUSTERS},
        "computation": {"enabled": app_settings.is_enabled("WEBSERVER_COMPUTATION")},
        "diagnostics": {"enabled": app_settings.is_enabled("WEBSERVER_DIAGNOSTICS")},
        "director-v2": {"enabled": app_settings.is_enabled("WEBSERVER_DIRECTOR_V2")},
        "exporter": {"enabled": app_settings.WEBSERVER_EXPORTER is not None},
        "groups": {"enabled": app_settings.WEBSERVER_GROUPS},
        "meta_modeling": {"enabled": app_settings.WEBSERVER_META_MODELING},
        "products": {"enabled": app_settings.WEBSERVER_PRODUCTS},
        "publications": {"enabled": app_settings.WEBSERVER_PUBLICATIONS},
        "remote_debug": {"enabled": app_settings.WEBSERVER_REMOTE_DEBUG},
        "security": {"enabled": True},
        "statics": {
            "enabled": app_settings.WEBSERVER_FRONTEND is not None
            and app_settings.WEBSERVER_STATICWEB is not None
        },
        # NOTE:  app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED did not apply
        "studies_access": {"enabled": app_settings.WEBSERVER_STUDIES_ACCESS},
        # NOTE  app_settings.WEBSERVER_STUDIES_ACCESS_ENABLED did not apply
        "studies_dispatcher": {"enabled": app_settings.WEBSERVER_STUDIES_DISPATCHER},
        "tags": {"enabled": app_settings.WEBSERVER_TAGS},
        "users": {"enabled": app_settings.WEBSERVER_USERS},
        "version_control": {"enabled": app_settings.WEBSERVER_VERSION_CONTROL},
    }

    return cfg


def convert_to_environ_vars(cfg: Dict[str, Any]) -> Dict[str, Any]:
    # NOTE: maily used for testing traferet vs settings_library
    # pylint:disable=too-many-branches
    # pylint:disable=too-many-statements
    envs = {}

    def _set_enable(section_name, section):
        if not section.get("enabled"):
            envs[section_name] = "null"

    if main := cfg.get("main"):
        envs["WEBSERVER_PORT"] = main.get("port")
        envs["WEBSERVER_LOG_LEVEL"] = main.get("log_level")
        envs["WEBSERVER_STUDIES_ACCESS_ENABLED"] = main.get("studies_access_enabled")

    if section := cfg.get("tracing"):
        _set_enable("WEBSERVER_TRACING", section)
        envs["TRACING_ZIPKIN_ENDPOINT"] = section.get("zipkin_endpoint")

    if section := cfg.get("director"):
        _set_enable("WEBSERVER_DIRECTOR", section)
        envs["DIRECTOR_HOST"] = section.get("host")
        envs["DIRECTOR_PORT"] = section.get("port")
        envs["DIRECTOR_VTAG"] = section.get("version")

    if db := cfg.get("db"):
        if section := db.get("postgres"):

            envs["POSTGRES_DB"] = section.get("database")
            envs["POSTGRES_HOST"] = section.get("host")
            envs["POSTGRES_MAXSIZE"] = section.get("maxsize")
            envs["POSTGRES_MINSIZE"] = section.get("minsize")
            envs["POSTGRES_PASSWORD"] = section.get("password")
            envs["POSTGRES_PORT"] = section.get("port")
            envs["POSTGRES_USER"] = section.get("user")

        _set_enable("WEBSERVER_DB", db)

    if section := cfg.get("resource_manager"):
        _set_enable("WEBSERVER_RESOURCE_MANAGER", section)

        envs["WEBSERVER_RESOURCES_DELETION_TIMEOUT_SECONDS"] = section.get(
            "resource_deletion_timeout_seconds"
        )
        envs["WEBSERVER_GARBAGE_COLLECTION_INTERVAL_SECONDS"] = section.get(
            "garbage_collection_interval_seconds"
        )

        if section2 := section.get("redis"):
            _set_enable("WEBSERVER_REDIS", section2)
            envs["REDIS_HOST"] = section2.get("host")
            envs["REDIS_PORT"] = section2.get("port")

    if section := cfg.get("login"):
        _set_enable("WEBSERVER_LOGIN", section)

        envs["LOGIN_REGISTRATION_INVITATION_REQUIRED"] = section.get(
            "registration_invitation_required"
        )
        envs["LOGIN_REGISTRATION_CONFIRMATION_REQUIRED"] = section.get(
            "registration_confirmation_required"
        )

    if section := cfg.get("smtp"):
        envs["SMTP_SENDER"] = section.get("sender")
        envs["SMTP_HOST"] = section.get("host")
        envs["SMTP_PORT"] = section.get("port")
        envs["SMTP_TLS_ENABLED"] = section.get("tls")

        envs["SMTP_USERNAME"] = section.get("username")
        envs["SMTP_PASSWORD"] = section.get("password")

    if section := cfg.get("storage"):
        _set_enable("WEBSERVER_STORAGE", section)

        envs["STORAGE_HOST"] = section.get("host")
        envs["STORAGE_PORT"] = section.get("port")
        envs["STORAGE_VTAG"] = section.get("version")

    if section := cfg.get("catalog"):
        _set_enable("WEBSERVER_CATALOG", section)

        envs["CATALOG_HOST"] = section.get("host")
        envs["CATALOG_PORT"] = section.get("port")
        envs["CATALOG_VTAG"] = section.get("version")

    if section := cfg.get("session"):
        envs["SESSION_SECRET_KEY"] = section.get("secret_key")

    if section := cfg.get("activity"):
        _set_enable("WEBSERVER_ACTIVITY", section)

        envs["PROMETHEUS_PORT"] = section.get("prometheus_port")
        envs["PROMETHEUS_VTAG"] = section.get("prometheus_api_version")

    if section := cfg.get("computation"):
        _set_enable("COMPUTATION", section)

    if section := cfg.get("diagnostics"):
        _set_enable("DIAGNOSTICS", section)

    if section := cfg.get("director-v2"):
        _set_enable("DIRECTOR_V2", section)

    if section := cfg.get("exporter"):
        _set_enable("WEBSERVER_EXPORTER", section)

    if section := cfg.get("statics"):
        _set_enable("WEBSERVER_FRONTEND", section)
        _set_enable("WEBSERVER_STATICWEB", section)

    return {k: v for k, v in envs.items() if v is not None}
