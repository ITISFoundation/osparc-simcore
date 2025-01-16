from aiohttp import web
from pydantic import Field, NonNegativeInt
from settings_library.base import BaseCustomSettings

from .._constants import APP_SETTINGS_KEY


class TrashSettings(BaseCustomSettings):
    TRASH_RETENTION_DAYS: NonNegativeInt = Field(
        default=7,
        description="Number of days that trashed items are kept in the bin before finally deleting them",
    )


def get_plugin_settings(app: web.Application) -> TrashSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_TRASH
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, TrashSettings)  # nosec
    return settings
