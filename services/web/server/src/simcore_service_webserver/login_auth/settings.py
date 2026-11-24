from typing import Annotated

from pydantic import Field
from settings_library.base import BaseCustomSettings

from ..login.settings import LoginThrottleSettings


class LoginAuthSettings(BaseCustomSettings):
    LOGIN_THROTTLE: Annotated[
        LoginThrottleSettings,
        Field(
            json_schema_extra={"auto_default_from_env": True},
            description="Login throttle settings, same as in the webserver",
        ),
    ]
