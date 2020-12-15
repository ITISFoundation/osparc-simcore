from enum import Enum

from pydantic import conint, constr, confloat, BaseModel, error_wrappers

PortInt = conint(gt=0, lt=65535)

VersionTag = constr(regex=r"^v\d$")

NonNegativeFloat = confloat(ge=0)  # NOTE: = 0.0 + PositiveFloat


class StringBool(BaseModel):
    __root__: bool

    @classmethod
    def parse(cls, str_bool: str) -> bool:
        try:
            value = StringBool.parse_obj(str_bool)
            return value.__root__
        except error_wrappers.ValidationError:
            return False


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BootModeEnum(str, Enum):
    """
    Values taken by SC_BOOT_MODE environment variable
    set in Dockerfile and used during docker/boot.sh
    """

    DEFAULT = "default"
    LOCAL = "local-development"
    DEBUG = "debug-ptvsd"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


class BuildTargetEnum(str, Enum):
    """
    Values taken by SC_BUILD_TARGET environment variable
    set in Dockerfile that defines the stage targeted in the
    docker image build
    """

    BUILD = "build"
    CACHE = "cache"
    PRODUCTION = "production"
    DEVELOPMENT = "development"
