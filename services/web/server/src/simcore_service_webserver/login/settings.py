""" login subsystem's configuration

    - config-file schema
    - settings
"""

from aiohttp import web
from aiohttp.web import Application
from pydantic import Field
from settings_library.base import BaseCustomSettings

from .config import get_login_config

APP_LOGIN_CONFIG = __name__ + ".config"
CFG_LOGIN_STORAGE = "STORAGE"  # Needs to match login.cfg!!!


def get_storage(app: web.Application):
    return app[APP_LOGIN_CONFIG][CFG_LOGIN_STORAGE]


class LoginSettings(BaseCustomSettings):
    LOGIN_REGISTRATION_CONFIRMATION_REQUIRED: bool = Field(
        ...,
        env=[
            "LOGIN_REGISTRATION_CONFIRMATION_REQUIRED",
            "WEBSERVER_LOGIN_REGISTRATION_CONFIRMATION_REQUIRED",
        ],
    )
    LOGIN_REGISTRATION_INVITATION_REQUIRED: bool = Field(
        ...,
        env=[
            "LOGIN_REGISTRATION_INVITATION_REQUIRED",
            "WEBSERVER_LOGIN_REGISTRATION_INVITATION_REQUIRED",
        ],
    )


def assert_valid_config(app: Application):
    """
    raises pydantic.ValidationError if validation fails
    """
    cfg = get_login_config(app)

    WEBSERVER_LOGIN = LoginSettings()

    assert cfg == {  # nosec
        "enabled": WEBSERVER_LOGIN is not None,
        "registration_invitation_required": 1
        if WEBSERVER_LOGIN.LOGIN_REGISTRATION_INVITATION_REQUIRED
        else 0,
        "registration_confirmation_required": 1
        if WEBSERVER_LOGIN.LOGIN_REGISTRATION_CONFIRMATION_REQUIRED
        else 0,
    }

    return cfg, WEBSERVER_LOGIN
