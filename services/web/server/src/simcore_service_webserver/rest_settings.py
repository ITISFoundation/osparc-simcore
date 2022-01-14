""" rest subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

from aiohttp import web
from models_library.basic_types import VersionTag
from pydantic import BaseSettings, Field

from ._meta import API_VTAG
from .rest_config import get_rest_config


class RestApiSettings(BaseSettings):
    enabled: Optional[bool] = True
    vtag: VersionTag = Field(
        API_VTAG, alias="version", description="web-server API's version tag"
    )


def assert_valid_config(app: web.Application) -> Dict:
    cfg = get_rest_config(app)
    _settings = RestApiSettings(**cfg)
    return cfg
