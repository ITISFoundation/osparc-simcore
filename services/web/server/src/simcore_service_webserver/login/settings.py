""" login subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

from aiohttp.web import Application
from pydantic import BaseSettings

from .cfg import DEFAULTS
from .config import get_login_config


class LoginSettings(BaseSettings):
    enabled: bool = True
    registration_confirmation_required: Optional[bool] = DEFAULTS[
        "REGISTRATION_CONFIRMATION_REQUIRED"
    ]
    registration_invitation_required: Optional[bool] = False

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_"


def assert_valid_config(app: Application) -> Dict:
    """
    raises pydantic.ValidationError if validation fails
    """
    cfg = get_login_config(app)
    _settings = LoginSettings(**cfg)
    return cfg
