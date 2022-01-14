""" app's configuration

    This module loads the schema defined by every subsystem and injects it in the
    application's configuration scheams

    It was designed in a similar fashion to the setup protocol of the application
    where every subsystem is imported and queried in a specific order. The application
    depends on the subsystem and not the other way around.

    The app configuration is created before the application instance exists.

"""
import logging
from typing import Dict

from aiohttp.web import Application
from models_library.basic_types import LogLevel, PortInt
from pydantic import BaseSettings, Field
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

log = logging.getLogger(__name__)


class MainSettings(BaseSettings):
    host: str = "0.0.0.0"  # nosec
    port: PortInt = 8080
    log_level: LogLevel = Field(LogLevel.INFO, env="WEBSERVER_LOGLEVEL")
    testing: bool = False
    studies_access_enabled: bool = False

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_"


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY]["main"]
    _settings = MainSettings(**cfg)
    return cfg
