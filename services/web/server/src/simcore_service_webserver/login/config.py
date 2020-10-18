""" login subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Optional

import trafaret as T
from pydantic import BaseSettings

from .cfg import DEFAULTS

CONFIG_SECTION_NAME = "login"

# TODO: merge with cfg.py
schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key(
            "registration_confirmation_required",
            default=DEFAULTS["REGISTRATION_CONFIRMATION_REQUIRED"],
            optional=True,
        ): T.Or(T.Bool, T.ToInt),
        T.Key("registration_invitation_required", default=False, optional=True): T.Or(
            T.Bool, T.ToInt
        ),
    }
)


class LoginSettings(BaseSettings):
    registration_confirmation_required: Optional[bool] = DEFAULTS[
        "REGISTRATION_CONFIRMATION_REQUIRED"
    ]
    registration_invitation_required: Optional[bool] = False

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_"


def get_login_config(app):
    from servicelib.application_keys import APP_CONFIG_KEY

    cfg = app[APP_CONFIG_KEY].get(CONFIG_SECTION_NAME, dict())
    return cfg
