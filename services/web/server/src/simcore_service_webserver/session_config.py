""" session subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T
from pydantic import BaseSettings, constr

CONFIG_SECTION_NAME = "session"

schema = T.Dict({"secret_key": T.String})


class SessionSettings(BaseSettings):
    secret_key: constr(strip_whitespace=True, min_length=32, max_length=21)
