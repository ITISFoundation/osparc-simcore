from typing import Dict

from aiohttp.web import Application
from servicelib.aiohttp.application_keys import APP_CONFIG_KEY

from ..email_settings import SmtpSettings
from .storage import AsyncpgStorage

CONFIG_SECTION_NAME = "login"


def create_login_internal_config(
    app: Application, storage: AsyncpgStorage, email_settings: SmtpSettings
) -> Dict:
    """
    Creates compatible config to update login.cfg.cfg object
    """

    config = {
        "APP": app,
        "STORAGE": storage,
    }

    config.update(
        {
            "SMTP_SENDER": email_settings.SMTP_SENDER,
            "SMTP_HOST": email_settings.SMTP_HOST,
            "SMTP_PORT": email_settings.SMTP_PORT,
            "SMTP_TLS_ENABLED": email_settings.SMTP_TLS_ENABLED,
            "SMTP_USERNAME": email_settings.SMTP_USERNAME,
            "SMTP_PASSWORD": email_settings.SMTP_PASSWORD.get_secret_value(),
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
