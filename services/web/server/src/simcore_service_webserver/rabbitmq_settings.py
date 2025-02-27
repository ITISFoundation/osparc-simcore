""" computation subsystem's configuration

    - config-file schema
    - settings
"""


from aiohttp.web import Application
from settings_library.rabbit import RabbitSettings

from .constants import APP_SETTINGS_KEY


def get_plugin_settings(app: Application) -> RabbitSettings:
    settings: RabbitSettings | None = app[APP_SETTINGS_KEY].WEBSERVER_RABBITMQ
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, RabbitSettings)  # nosec
    return settings


__all__: tuple[str, ...] = (
    "RabbitSettings",
    "get_plugin_settings",
)
