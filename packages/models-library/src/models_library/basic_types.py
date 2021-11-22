from enum import Enum

from pydantic import conint, constr

from .basic_regex import VERSION_RE

# port number range
PortInt = conint(gt=0, lt=65535)

# e.g. 'v5'
VersionTag = constr(regex=r"^v\d$")

# e.g. '1.23.11' or '2.1.0-rc2'
VersionStr = constr(regex=VERSION_RE)

# checksums
SHA1Str = constr(regex=r"^[a-fA-F0-9]{40}$")
MD5Str = constr(regex=r"^[a-fA-F0-9]{32}$")


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
