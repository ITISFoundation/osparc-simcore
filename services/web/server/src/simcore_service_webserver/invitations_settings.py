""" Settings for the invitations plugin

NOTE: do not move them to settings_library since (so far) only the
webserver should interact with this
"""

from functools import cached_property

from aiohttp import web
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)

from ._constants import APP_SETTINGS_KEY


class InvitationsSettings(BaseCustomSettings, MixinServiceSettings):
    INVITATIONS_HOST: str = "invitations"
    INVITATIONS_PORT: PortInt = DEFAULT_FASTAPI_PORT
    INVITATIONS_VTAG: VersionTag = "v1"

    @cached_property
    def api_base_url(self) -> str:
        # http://invitations:8000/v1
        return self._compose_url(
            prefix="INVITATIONS",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )

    @cached_property
    def base_url(self) -> str:
        # http://invitations:8000
        return self._compose_url(
            prefix="INVITATIONS",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )


def get_plugin_settings(app: web.Application) -> InvitationsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, InvitationsSettings)  # nosec
    return settings
