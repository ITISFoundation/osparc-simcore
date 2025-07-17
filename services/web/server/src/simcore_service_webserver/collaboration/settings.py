from typing import Annotated

from aiohttp import web
from pydantic import (
    PositiveInt,
)
from pydantic.fields import Field
from settings_library.base import BaseCustomSettings

from ..constants import APP_SETTINGS_KEY


class RealTimeCollaborationSettings(BaseCustomSettings):
    RTC_MAX_NUMBER_OF_USERS: Annotated[
        PositiveInt,
        Field(
            description="Maximum number of users allowed in a real-time collaboration session",
        ),
    ]


def get_plugin_settings(app: web.Application) -> RealTimeCollaborationSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_REALTIME_COLLABORATION
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, RealTimeCollaborationSettings)  # nosec
    return settings
