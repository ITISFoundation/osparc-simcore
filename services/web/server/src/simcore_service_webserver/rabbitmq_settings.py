""" computation subsystem's configuration

    - config-file schema
    - settings
"""


from aiohttp.web import Application
from settings_library.rabbit import RabbitSettings

from ._constants import APP_SETTINGS_KEY


def get_plugin_settings(app: Application) -> RabbitSettings:
    settings: RabbitSettings = app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, RabbitSettings)  # nosec
    return settings
