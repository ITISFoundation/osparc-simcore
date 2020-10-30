""" projects subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Optional

import trafaret as T
from pydantic import BaseSettings
from servicelib.application_keys import APP_CONFIG_KEY
from aiohttp.web import Application
from typing import Dict

CONFIG_SECTION_NAME = "projects"

schema = T.Dict({T.Key("enabled", default=True, optional=True): T.Bool()})


class ProjectSettings(BaseSettings):
    enabled: Optional[bool] = True


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = ProjectSettings(**cfg)
    return cfg
