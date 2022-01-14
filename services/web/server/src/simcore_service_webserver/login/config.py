""" login subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict

from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from ..email_config import CONFIG_SECTION_NAME as SMTP_SECTION
from ._schema import CONFIG_SECTION_NAME
from .storage import AsyncpgStorage


def get_login_config(app: Application) -> Dict:

    cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, {})
    return cfg


def create_login_internal_config(app: Application, storage: AsyncpgStorage) -> Dict:
    """
    Creates compatible config to update login.cfg.cfg object
    """
    login_cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, {})  # optional!
    smtp_cfg = app[APP_CONFIG_KEY][SMTP_SECTION]

    config = {"APP": app, "STORAGE": storage}

    def _fmt(val):
        if isinstance(val, str):
            if val.strip().lower() in ["null", "none", ""]:
                return None
        return val

    for key, value in login_cfg.items():
        config[key.upper()] = _fmt(value)

    for key, value in smtp_cfg.items():
        config["SMTP_{}".format(key.upper())] = _fmt(value)

    return config
