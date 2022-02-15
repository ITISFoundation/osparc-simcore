""" computation subsystem's configuration

    - config-file schema
    - settings
"""

from typing import Optional

from aiohttp.web import Application
from settings_library.rabbit import RabbitSettings

from ._constants import APP_SETTINGS_KEY


def get_plugin_settings(app: Application) -> RabbitSettings:
    settings: Optional[RabbitSettings] = app[APP_SETTINGS_KEY].WEBSERVER_COMPUTATION
    assert settings  # nosec
    return settings
