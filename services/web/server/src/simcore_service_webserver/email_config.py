""" email's subsystem's configuration

    - config-file schema
    - settings
"""
from typing import Optional

import trafaret as T
from models_library.settings import PortInt
from pydantic import BaseSettings

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
