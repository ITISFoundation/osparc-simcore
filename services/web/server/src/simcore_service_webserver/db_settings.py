from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from settings_library.postgres import PostgresSettings

from .db_config import CONFIG_SECTION_NAME


def assert_valid_config(app: Application):
    import json

    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    WEBSERVER_POSTGRES = PostgresSettings()
    got = {  # nosec
        "postgres": {
            "database": WEBSERVER_POSTGRES.POSTGRES_DB,
            "endpoint": f"{WEBSERVER_POSTGRES.POSTGRES_HOST}:{WEBSERVER_POSTGRES.POSTGRES_PORT}",
            "host": WEBSERVER_POSTGRES.POSTGRES_HOST,
            "maxsize": WEBSERVER_POSTGRES.POSTGRES_MAXSIZE,
            "minsize": WEBSERVER_POSTGRES.POSTGRES_MINSIZE,
            "password": WEBSERVER_POSTGRES.POSTGRES_PASSWORD.get_secret_value(),
            "port": WEBSERVER_POSTGRES.POSTGRES_PORT,
            "user": WEBSERVER_POSTGRES.POSTGRES_USER,
        },
        "enabled": WEBSERVER_POSTGRES is not None,
    }
    assert cfg == got, json.dumps(got) + "!=" + json.dumps(cfg)
    return cfg, PostgresSettings
