from enum import Enum

from pydantic import ConstrainedInt, HttpUrl, PositiveInt, constr

from .basic_regex import UUID_RE, VERSION_RE


# port number range
class PortInt(ConstrainedInt):
    gt = 0
    lt = 65535


# e.g. 'v5'
VersionTag = constr(regex=r"^v\d$")

# e.g. '1.23.11' or '2.1.0-rc2'
VersionStr = constr(regex=VERSION_RE)

# checksums
SHA1Str = constr(regex=r"^[a-fA-F0-9]{40}$")
MD5Str = constr(regex=r"^[a-fA-F0-9]{32}$")

# env var
EnvVarKey = constr(regex=r"[a-zA-Z][a-azA-Z0-9_]*")

# e.g. '5c833a78-1af3-43a7-9ed7-6a63b188f4d8'
UUIDStr = constr(regex=UUID_RE)

# auto-incremented primary-key IDs
IdInt = PrimaryKeyInt = PositiveInt

# https e.g. https://techterms.com/definition/https
class HttpSecureUrl(HttpUrl):
    allowed_schemes = {"https"}


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

    def is_devel_mode(self) -> bool:
        """returns True if this boot mode is used for development"""
        return self in (self.DEBUG, self.DEVELOPMENT, self.LOCAL)


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
