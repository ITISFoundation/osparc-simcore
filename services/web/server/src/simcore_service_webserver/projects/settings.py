""" projects subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

from aiohttp.web import Application
from pydantic import BaseSettings
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from .config import CONFIG_SECTION_NAME


class ProjectSettings(BaseSettings):
    enabled: Optional[bool] = True


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = ProjectSettings(**cfg)
    return cfg
