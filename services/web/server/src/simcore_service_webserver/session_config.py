""" session subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T
from pydantic import BaseSettings, constr
from servicelib.application_keys import APP_CONFIG_KEY
from aiohttp.web import Application
from typing import Dict

CONFIG_SECTION_NAME = "session"

schema = T.Dict({"secret_key": T.String})


class SessionSettings(BaseSettings):
    secret_key: constr(strip_whitespace=True, min_length=32)


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = SessionSettings(**cfg)
    return cfg
