""" director v2 susystem configuration
"""

from functools import cached_property

from aiohttp import ClientSession, ClientTimeout, web
from models_library.basic_types import PortInt, VersionTag
from pydantic import Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_CLIENT_SESSION_KEY
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import (
    DEFAULT_FASTAPI_PORT,
    MixinServiceSettings,
    URLPart,
)
from yarl import URL

from ._constants import APP_SETTINGS_KEY

_MINUTE = 60
_HOUR = 60 * _MINUTE


class DirectorV2Settings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_V2_HOST: str = "director-v2"
    DIRECTOR_V2_PORT: PortInt = DEFAULT_FASTAPI_PORT
    DIRECTOR_V2_VTAG: VersionTag = "v2"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR_V2"))

    @cached_property
    def base_url_no_vtag(self) -> URL:
        return URL(self._compose_url(prefix="DIRECTOR_V2", port=URLPart.REQUIRED))

    # DESIGN NOTE:
    # - Timeouts are typically used in clients (total/read/connection timeouts) or asyncio calls
    # - Mostly in floats (aiohttp.Client/) but sometimes in ints
    # - Typically in seconds but occasionally in ms
    DIRECTOR_V2_STOP_SERVICE_TIMEOUT: PositiveInt = Field(
        _HOUR + 10,
        description=(
            "Timeout on stop service request (seconds)"
            "ANE: The below will try to help explaining what is happening: "
            "webserver -(stop_service)-> director-v* -(save_state)-> service_x"
            "- webserver requests stop_service and uses a 01:00:10 timeout"
            "- director-v* requests save_state and uses a 01:00:00 timeout"
            "The +10 seconds is used to make sure the director replies"
        ),
        envs=[
            "DIRECTOR_V2_STOP_SERVICE_TIMEOUT",
            # TODO: below this line are deprecated. rm when deveops give OK
            "WEBSERVER_DIRECTOR_STOP_SERVICE_TIMEOUT",
            "webserver_director_stop_service_timeout",
        ],
    )

    DIRECTOR_V2_RESTART_DYNAMIC_SERVICE_TIMEOUT: PositiveInt = Field(
        1 * _MINUTE,
        description="timeout of containers restart",
        envs=[
            "DIRECTOR_V2_RESTART_DYNAMIC_SERVICE_TIMEOUT",
            # TODO: below this line are deprecated. rm when deveops give OK
            "SERVICES_COMMON_RESTART_CONTAINERS_TIMEOUT",
            "SERVICES_COMMON_restart_containers_timeout",
        ],
    )

    DIRECTOR_V2_NETWORK_ATTACH_DETACH_TIMEOUT: PositiveInt = Field(
        1 * _MINUTE, description="timeout to attach/detach a network"
    )

    DIRECTOR_V2_STORAGE_SERVICE_UPLOAD_DOWNLOAD_TIMEOUT: PositiveInt = Field(
        _HOUR,
        description=(
            "When dynamic services upload and download data from storage, "
            "sometimes very big payloads are involved. In order to handle "
            "such payloads it is required to have long timeouts which "
            "allow the service to finish the operation."
        ),
        envs=[
            "DIRECTOR_V2_DYNAMIC_SERVICE_DATA_UPLOAD_DOWNLOAD_TIMEOUT",
            # TODO: below this line are deprecated. rm when deveops give OK
            "SERVICES_COMMON_STORAGE_SERVICE_UPLOAD_DOWNLOAD_TIMEOUT",
            "SERVICES_COMMON_storage_service_upload_download_timeout",
        ],
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
    return app[APP_CLIENT_SESSION_KEY]
