""" login subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Dict, Optional

from aiohttp.web import Application
from pydantic import BaseSettings
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from ..constants import APP_SETTINGS_KEY
from ..email_settings import EmailSettings
from .cfg import DEFAULTS
from .storage import AsyncpgStorage

CONFIG_SECTION_NAME = "login"


class LoginSettings(BaseSettings):
    enabled: bool = True
    registration_confirmation_required: Optional[bool] = DEFAULTS[
        "REGISTRATION_CONFIRMATION_REQUIRED"
    ]
    registration_invitation_required: Optional[bool] = False

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_"


def get_login_config(app: Application) -> Dict:

    cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, {})
    return cfg


def assert_valid_config(app: Application) -> Dict:
    """
    raises pydantic.ValidationError if validation fails
    """
    cfg = get_login_config(app)
    _settings = LoginSettings(**cfg)
    return cfg


def create_login_internal_config(app: Application, storage: AsyncpgStorage) -> Dict:
    """
    Creates compatible config to update login.cfg.cfg object
    """

    config = {
        "APP": app,
        "STORAGE": storage,
    }

    email_settings: EmailSettings = app[APP_SETTINGS_KEY].WEBSERVER_EMAIL
    config.update(
        {
            "SMTP_SENDER": email_settings.EMAIL_SENDER,
            "SMTP_HOST": email_settings.EMAIL_SMTP.SMTP_HOST,
            "SMTP_PORT": email_settings.EMAIL_SMTP.SMTP_PORT,
            "SMTP_TLS_ENABLED": email_settings.EMAIL_SMTP.SMTP_TLS_ENABLED,
            "SMTP_USERNAME": email_settings.EMAIL_SMTP.SMTP_USERNAME,
            "SMTP_PASSWORD": email_settings.EMAIL_SMTP.SMTP_PASSWORD.get_secret_value(),
        }
    )

    def _fmt(val):
        if isinstance(val, str):
            if val.strip().lower() in ["null", "none", ""]:
                return None
        return val

    login_cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, {})  # optional!

    for key, value in login_cfg.items():
        config[key.upper()] = _fmt(value)

    return config
