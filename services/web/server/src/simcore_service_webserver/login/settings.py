from aiohttp import web
from pydantic import Field
from settings_library.base import BaseCustomSettings

APP_LOGIN_CONFIG = __name__ + ".config"
CFG_LOGIN_STORAGE = "STORAGE"  # Needs to match login.cfg!!!


def get_storage(app: web.Application):
    return app[APP_LOGIN_CONFIG][CFG_LOGIN_STORAGE]


class LoginSettings(BaseCustomSettings):
    LOGIN_REGISTRATION_CONFIRMATION_REQUIRED: bool = Field(
        ..., env=["WEBSERVER_LOGIN_REGISTRATION_CONFIRMATION_REQUIRED"]
    )
    LOGIN_REGISTRATION_INVITATION_REQUIRED: bool = Field(
        ..., env=["WEBSERVER_LOGIN_REGISTRATION_INVITATION_REQUIRED"]
    )
