""" projects subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Optional

import trafaret as T
from pydantic import BaseSettings

CONFIG_SECTION_NAME = "projects"

schema = T.Dict({T.Key("enabled", default=True, optional=True): T.Bool()})


class ProjectSettings(BaseSettings):
    enabled: Optional[bool] = True
