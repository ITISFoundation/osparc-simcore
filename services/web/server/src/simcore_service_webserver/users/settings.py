from aiohttp import web
from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr
from settings_library.base import BaseCustomSettings
from settings_library.utils_service import MixinServiceSettings

from ..constants import APP_SETTINGS_KEY


class UsersSettings(BaseCustomSettings, MixinServiceSettings):
    USERS_FRONTEND_PREFERENCES_DEFAULTS_OVERWRITES: dict[
        str, StrictInt | StrictFloat | StrictStr | StrictBool | list | dict | None
    ] = Field(
        default_factory=dict,
        description="key: name of the FrontendUserPreference, value: new default",
    )


def get_plugin_settings(app: web.Application) -> UsersSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_USERS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, UsersSettings)  # nosec
    return settings
