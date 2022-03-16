from functools import cached_property

from aiohttp.web import Application
from models_library.basic_types import PortInt, VersionTag
from pydantic import Field, PositiveInt
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import DEFAULT_AIOHTTP_PORT, MixinServiceSettings
from yarl import URL

from .._constants import APP_SETTINGS_KEY

_MINUTE = 60
_HOUR = 60 * _MINUTE


class DirectorSettings(BaseCustomSettings, MixinServiceSettings):
    DIRECTOR_HOST: str = "director"
    DIRECTOR_PORT: PortInt = DEFAULT_AIOHTTP_PORT
    DIRECTOR_VTAG: VersionTag = "v0"

    @cached_property
    def base_url(self) -> URL:
        return URL(self._build_api_base_url(prefix="DIRECTOR"))

    # DESIGN NOTE:
    # - Timeouts are typically used in clients (total/read/connection timeouts) or asyncio calls
    # - Mostly in floats (aiohttp.Client/) but sometimes in ints
    # - Typically in seconds but occasionally in ms
    DIRECTOR_STOP_SERVICE_TIMEOUT: PositiveInt = Field(
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
            "DIRECTOR_STOP_SERVICE_TIMEOUT",
            "webserver_director_stop_service_timeout",  # TODO: deprecated. rm when deveops give OK
        ],
    )


def get_plugin_settings(app: Application) -> DirectorSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_DIRECTOR
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, DirectorSettings)  # nosec
    return settings
