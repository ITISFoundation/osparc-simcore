""" Settings for the invitations plugin

NOTE: do not move them to settings_library since (so far) only the
webserver should interact with this
"""

from functools import cached_property
from typing import Final

from aiohttp import web
from pydantic import Field, SecretStr, TypeAdapter
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt, VersionTag
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)

from .._constants import APP_SETTINGS_KEY

_INVITATION_VTAG_V1: Final[VersionTag] = TypeAdapter(VersionTag).validate_python("v1")


class InvitationsSettings(BaseCustomSettings, MixinServiceSettings):
    INVITATIONS_HOST: str = "invitations"
    INVITATIONS_PORT: PortInt = DEFAULT_FASTAPI_PORT
    INVITATIONS_VTAG: VersionTag = _INVITATION_VTAG_V1

    INVITATIONS_USERNAME: str = Field(
        ...,
        description="Username for HTTP Basic Auth. Required if started as a web app.",
        min_length=3,
    )
    INVITATIONS_PASSWORD: SecretStr = Field(
        ...,
        description="Password for HTTP Basic Auth. Required if started as a web app.",
        min_length=10,
    )

    @cached_property
    def api_base_url(self) -> str:
        # http://invitations:8000/v1
        base_url_with_vtag: str = self._compose_url(
            prefix="INVITATIONS",
            port=URLPart.REQUIRED,
            vtag=URLPart.REQUIRED,
        )
        return base_url_with_vtag

    @cached_property
    def base_url(self) -> str:
        # http://invitations:8000
        base_url_without_vtag: str = self._compose_url(
            prefix="INVITATIONS",
            port=URLPart.REQUIRED,
            vtag=URLPart.EXCLUDE,
        )
        return base_url_without_vtag


def get_plugin_settings(app: web.Application) -> InvitationsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, InvitationsSettings)  # nosec
    return settings
