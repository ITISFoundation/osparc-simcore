""" Activity manager configuration
    - config-file schema
    - prometheus endpoint information
"""
from typing import Dict

from aiohttp.web import Application
from models_library.basic_types import PortInt, VersionTag
from pydantic import BaseSettings
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from .config import CONFIG_SECTION_NAME


class ActivitySettings(BaseSettings):
    enabled: bool = True
    prometheus_host: str = "prometheus"
    prometheus_port: PortInt = 9090
    prometheus_api_version: VersionTag = "v1"

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_"


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = ActivitySettings(**cfg)
    return cfg
