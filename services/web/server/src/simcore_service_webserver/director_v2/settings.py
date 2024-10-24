""" director v2 susystem configuration
"""

from functools import cached_property
from typing import cast

from aiohttp import ClientSession, ClientTimeout, web
from models_library.basic_types import VersionTag
from pydantic import AliasChoices, Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_CLIENT_SESSION_KEY
from settings_library.base import BaseCustomSettings
from settings_library.basic_types import PortInt
from settings_library.utils_service import DEFAULT_FASTAPI_PORT, MixinServiceSettings
from yarl import URL

from .._constants import APP_SETTINGS_KEY

_MINUTE = 60
_HOUR = 60 * _MINUTE


class DirectorV2Settings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_V2_HOST: str = "director-v2"
    DIRECTOR_V2_PORT: PortInt = DEFAULT_FASTAPI_PORT
    DIRECTOR_V2_VTAG: VersionTag = VersionTag("v2")

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR_V2"))

    # DESIGN NOTE:
    # - Timeouts are typically used in clients (total/read/connection timeouts) or asyncio calls
    # - Mostly in floats (aiohttp.Client/) but sometimes in ints
    # - Typically in seconds but occasionally in ms

    DIRECTOR_V2_RESTART_DYNAMIC_SERVICE_TIMEOUT: PositiveInt = Field(
        1 * _MINUTE,
        description="timeout of containers restart",
        validation_alias=AliasChoices(
            "DIRECTOR_V2_RESTART_DYNAMIC_SERVICE_TIMEOUT",
        ),
    )

    DIRECTOR_V2_STORAGE_SERVICE_UPLOAD_DOWNLOAD_TIMEOUT: PositiveInt = Field(
        _HOUR,
        description=(
            "When dynamic services upload and download data from storage, "
            "sometimes very big payloads are involved. In order to handle "
            "such payloads it is required to have long timeouts which "
            "allow the service to finish the operation."
        ),
        validation_alias=AliasChoices(
            "DIRECTOR_V2_DYNAMIC_SERVICE_DATA_UPLOAD_DOWNLOAD_TIMEOUT",
        ),
    )

    def get_service_retrieve_timeout(self) -> ClientTimeout:
        return ClientTimeout(
            total=self.DIRECTOR_V2_STORAGE_SERVICE_UPLOAD_DOWNLOAD_TIMEOUT,
            connect=None,
            sock_connect=5,
        )


def get_plugin_settings(app: web.Application) -> DirectorV2Settings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR_V2
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, DirectorV2Settings)  # nosec
    return settings


def get_client_session(app: web.Application) -> ClientSession:
    return cast(ClientSession, app[APP_CLIENT_SESSION_KEY])
