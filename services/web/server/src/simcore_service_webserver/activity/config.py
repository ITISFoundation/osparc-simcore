""" Activity manager configuration
    - config-file schema
    - prometheus endpoint information
"""
from aiohttp.web import Application
import trafaret as T
from models_library.basic_types import PortInt, VersionTag
from pydantic import BaseSettings
from servicelib.application_keys import APP_CONFIG_KEY
from typing import Dict

CONFIG_SECTION_NAME = "activity"

schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key(
            "prometheus_host", default="http://prometheus", optional=False
        ): T.String(),
        T.Key("prometheus_port", default=9090, optional=False): T.ToInt(),
        T.Key("prometheus_api_version", default="v1", optional=False): T.String(),
    }
)


class ActivitySettings(BaseSettings):
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
