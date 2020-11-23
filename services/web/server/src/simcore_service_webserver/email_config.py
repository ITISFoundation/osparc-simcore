""" email's subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Optional

import trafaret as T
from models_library.basic_types import PortInt
from pydantic import BaseSettings
from servicelib.application_keys import APP_CONFIG_KEY

from typing import Dict

from aiohttp.web import Application


CONFIG_SECTION_NAME = "smtp"


schema = T.Dict(
    {
        T.Key(
            "sender", default="OSPARC support <support@osparc.io>"
        ): T.String(),  # FIXME: email format
        "host": T.String(),
        "port": T.ToInt(),
        T.Key("tls", default=False): T.Or(T.Bool(), T.ToInt),
        T.Key("username", default=None): T.Or(T.String, T.Null),
        T.Key("password", default=None): T.Or(T.String, T.Null),
    }
)


class EmailSettings(BaseSettings):
    sender: str = "OSPARC support <support@osparc.io>"
    host: str
    port: PortInt
    tls: bool = False
    username: Optional[str] = None
    password: Optional[str] = None


def assert_valid_config(app: Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    _settings = EmailSettings(**cfg)
    return cfg
