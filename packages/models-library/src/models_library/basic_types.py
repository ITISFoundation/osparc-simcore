from enum import Enum

from pydantic import conint, constr, confloat

PortInt = conint(gt=0, lt=65535)

VersionTag = constr(regex=r"^v\d$")

NonNegativeFloat = confloat(ge=0)  # NOTE: = 0.0 + PositiveFloat


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BootModeEnum(str, Enum):
    LOCAL = "local-development"
    DEBUG = "debug-ptvsd"
    PRODUCTION = "production"
    DEVELOPMENT = "development"
