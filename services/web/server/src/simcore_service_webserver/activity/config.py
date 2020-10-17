""" Activity manager configuration
    - config-file schema
    - prometheus endpoint information
"""
from typing import Optional

import trafaret as T
from models_library.settings import PortInt, VersionTag
from pydantic import BaseSettings

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
    enabled: Optional[bool] = True
    prometheus_host: str = "prometheus"
    prometheus_port: PortInt = 9090
    prometheus_api_version: VersionTag = "v1"
