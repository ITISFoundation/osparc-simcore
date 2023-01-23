""" Settings for the invitations plugin

NOTE: do not move them to settings_library since (so far) only the
webserver should interact with this
"""

from functools import cached_property
from typing import Optional

from aiohttp import web
from pydantic import Field, SecretStr, root_validator
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

    INVITATIONS_USERNAME: Optional[str] = Field(
        ...,
        description="Username for HTTP Basic Auth. Required if started as a web app.",
        min_length=3,
    )
    INVITATIONS_PASSWORD: Optional[SecretStr] = Field(
        ...,
        description="Password for HTTP Basic Auth. Required if started as a web app.",
        min_length=10,
    )

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

    @cached_property
    def is_auth_enabled(self) -> bool:
        return (
            self.INVITATIONS_USERNAME is not None
            and self.INVITATIONS_PASSWORD is not None
        )

    @root_validator
    @classmethod
    def check_complete_auth_state(cls, values):
        # either both None or none of them is None
        username = values.get("INVITATIONS_USERNAME")
        password = values.get("INVITATIONS_PASSWORD")

        if (username is None and password is not None) or (
            username is not None and password is None
        ):
            raise ValueError(
                f"To disable auth, set username==password==None. Partial None is not allowed, got {username=}, {password=}"
            )

        return values


def get_plugin_settings(app: web.Application) -> InvitationsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_INVITATIONS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, InvitationsSettings)  # nosec
    return settings
