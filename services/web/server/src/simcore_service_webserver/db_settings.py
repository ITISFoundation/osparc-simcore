from typing import Dict

from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY, APP_SETTINGS_KEY
from settings_library.postgres import PostgresSettings

from .db_config import CONFIG_SECTION_NAME


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]

    app_settings = app[APP_SETTINGS_KEY]

    assert isinstance(app_settings.WEBSERVER_POSTGRES, PostgresSettings)  # nosec
    assert app_settings.WEBSERVER_POSTGRES is not None

    assert cfg == {  # nosec
        "postgres": {
            "database": app_settings.WEBSERVER_POSTGRES.POSTGRES_DB,
            "endpoint": f"{app_settings.WEBSERVER_POSTGRES.POSTGRES_HOST}:{app_settings.WEBSERVER_POSTGRES.POSTGRES_PORT}",
            "host": app_settings.WEBSERVER_POSTGRES.POSTGRES_HOST,
            "maxsize": app_settings.WEBSERVER_POSTGRES.POSTGRES_MAXSIZE,
            "minsize": app_settings.WEBSERVER_POSTGRES.POSTGRES_MINSIZE,
            "password": app_settings.WEBSERVER_POSTGRES.POSTGRES_PASSWORD.get_secret_value(),
            "port": app_settings.WEBSERVER_POSTGRES.POSTGRES_PORT,
            "user": app_settings.WEBSERVER_POSTGRES.POSTGRES_USER,
        },
        "enabled": app_settings.WEBSERVER_POSTGRES is not None,
    }
    return cfg
