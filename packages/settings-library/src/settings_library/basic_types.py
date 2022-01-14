#
# NOTE: This files copies some of the types from models_library.basic_types
#       This is a minor evil to avoid the maintenance burden that creates
#       an extra dependency to a larger models_library (intra-repo library)

from enum import Enum

from pydantic.types import conint, constr

# port number range
PortInt = conint(gt=0, lt=65535)

# e.g. 'v5'
VersionTag = constr(regex=r"^v\d$")


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BootMode(str, Enum):
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
