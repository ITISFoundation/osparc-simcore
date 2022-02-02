from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from settings_library.postgres import PostgresSettings

from ._constants import APP_SETTINGS_KEY
from .db_config import CONFIG_SECTION_NAME


def assert_valid_config(app: Application):

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    cfg_enabled = cfg.pop("enabled")
    if app_settings := app.get(APP_SETTINGS_KEY):
        assert cfg_enabled == (app_settings.WEBSERVER_DB is not None)  # nosec

    # TODO: DEPRECATE: "endpoint": f"{WEBSERVER_POSTGRES.POSTGRES_HOST}:{WEBSERVER_POSTGRES.POSTGRES_PORT}",
    # NOTE: found inconsistencies between values passed as host and the entrypoint.
    # Remove and use instead WEBSERVER_POSTGRES.dsn
    cfg.get("postgres", {}).pop("endpoint", None)

    WEBSERVER_POSTGRES = PostgresSettings.create_from_envs()
    got = {  # nosec
        "postgres": {
            "database": WEBSERVER_POSTGRES.POSTGRES_DB,
            "host": WEBSERVER_POSTGRES.POSTGRES_HOST,
            "maxsize": WEBSERVER_POSTGRES.POSTGRES_MAXSIZE,
            "minsize": WEBSERVER_POSTGRES.POSTGRES_MINSIZE,
            "password": WEBSERVER_POSTGRES.POSTGRES_PASSWORD.get_secret_value(),
            "port": WEBSERVER_POSTGRES.POSTGRES_PORT,
            "user": WEBSERVER_POSTGRES.POSTGRES_USER,
        },
    }
    assert cfg == got, f"{got}!={cfg}"  # nosec
    return cfg, PostgresSettings
