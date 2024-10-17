from decimal import Decimal
from enum import StrEnum
from typing import Annotated, TypeAlias

from pydantic import Field, HttpUrl, PositiveInt, StringConstraints

from .basic_regex import (
    PROPERTY_KEY_RE,
    SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS,
    SIMPLE_VERSION_RE,
    UUID_RE,
)

NonNegativeDecimal: TypeAlias = Annotated[Decimal, Field(ge=0)]

PositiveDecimal: TypeAlias = Annotated[Decimal, Field(gt=0)]

# Used for amounts like credits or dollars
# NOTE: upper limit to avoid https://github.com/ITISFoundation/appmotion-exchange/issues/2
# NOTE: do not contraint in decimal places. Too strong validation error rather Decimal.quantize
# before passing the value
AmountDecimal: TypeAlias = Annotated[Decimal, Field(gt=0, lt=1e6)]

# port number range
PortInt: TypeAlias = Annotated[int, Field(gt=0, lt=65535)]


# https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers#Registered_ports
RegisteredPortInt: TypeAlias = Annotated[int, Field(gt=1024, lt=65535)]


# e.g. 'v5'
VersionTag: TypeAlias = Annotated[str, StringConstraints(pattern=r"^v\d$")]

VersionStr: TypeAlias = Annotated[str, StringConstraints(pattern=SIMPLE_VERSION_RE)]

# e.g. '1.23.11' or '2.1.0-rc2' or not 0.1.0-alpha  (see test_SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS)
SemanticVersionStr: TypeAlias = Annotated[
    str, StringConstraints(pattern=SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS)
]

# checksums
# sha1sum path/to/file
SHA1Str: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{40}$")]

# sha256sum path/to/file
SHA256Str: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{64}$")]

# md5sum path/to/file
MD5Str: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-fA-F0-9]{32}$")]

# env var
EnvVarKey: TypeAlias = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z]\w*")]

# e.g. '5c833a78-1af3-43a7-9ed7-6a63b188f4d8'
UUIDStr: TypeAlias = Annotated[str, StringConstraints(pattern=UUID_RE)]


# auto-incremented primary-key IDs
IdInt: TypeAlias = PositiveInt
PrimaryKeyInt: TypeAlias = PositiveInt


# https e.g. https://techterms.com/definition/https
class HttpSecureUrl(HttpUrl):
    allowed_schemes = {"https"}


class HttpUrlWithCustomMinLength(HttpUrl):
    # Overwriting min length to be back compatible when generating OAS
    min_length = 0


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class BootModeEnum(StrEnum):
    """
    Values taken by SC_BOOT_MODE environment variable
    set in Dockerfile and used during docker/boot.sh
    """

    DEFAULT = "default"
    LOCAL = "local-development"
    DEBUG = "debug"
    PRODUCTION = "production"
    DEVELOPMENT = "development"

    def is_devel_mode(self) -> bool:
        """returns True if this boot mode is used for development"""
        return self in (self.DEBUG, self.DEVELOPMENT, self.LOCAL)


class BuildTargetEnum(StrEnum):
    """
    Values taken by SC_BUILD_TARGET environment variable
    set in Dockerfile that defines the stage targeted in the
    docker image build
    """

    BUILD = "build"
    CACHE = "cache"
    PRODUCTION = "production"
    DEVELOPMENT = "development"


KeyIDStr = Annotated[str, StringConstraints(pattern=PROPERTY_KEY_RE)]
