""" computation subsystem's configuration

    - config-file schema
    - settings
"""

from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY
from settings_library.rabbit import RabbitSettings

from .computation_config import CONFIG_SECTION_NAME


class ComputationSettings(RabbitSettings):
    enabled: bool = True


def create_settings(app: Application) -> ComputationSettings:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    settings = ComputationSettings(**cfg)
    # NOTE: we are saving it in a separate item to config
    app[f"{__name__}.ComputationSettings"] = settings
    return settings


def get_settings(app: Application) -> ComputationSettings:
    return app[f"{__name__}.ComputationSettings"]
