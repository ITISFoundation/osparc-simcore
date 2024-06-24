import re
from enum import Enum
from typing import TypeAlias

from pydantic import (
    ConstrainedDecimal,
    ConstrainedInt,
    ConstrainedStr,
    HttpUrl,
    PositiveInt,
)

from .basic_regex import UUID_RE, VERSION_RE


class NonNegativeDecimal(ConstrainedDecimal):
    ge = 0


class PositiveDecimal(ConstrainedDecimal):
    gt = 0


class AmountDecimal(ConstrainedDecimal):
    # Used for amounts like credits or dollars
    # NOTE: upper limit to avoid https://github.com/ITISFoundation/appmotion-exchange/issues/2
    # NOTE: do not contraint in decimal places. Too strong validation error rather Decimal.quantize
    # before passing the value
    gt = 0
    lt = 1e6


# port number range
class PortInt(ConstrainedInt):
    gt = 0
    lt = 65535


# e.g. 'v5'
class VersionTag(ConstrainedStr):
    regex = re.compile(r"^v\d$")


# e.g. '1.23.11' or '2.1.0-rc2'
class VersionStr(ConstrainedStr):
    regex = re.compile(VERSION_RE)


# checksums
# sha1sum path/to/file
class SHA1Str(ConstrainedStr):
    regex = re.compile(r"^[a-fA-F0-9]{40}$")


# sha256sum path/to/file
class SHA256Str(ConstrainedStr):
    regex = re.compile(r"^[a-fA-F0-9]{64}$")


# md5sum path/to/file
class MD5Str(ConstrainedStr):
    regex = re.compile(r"^[a-fA-F0-9]{32}$")


# env var
class EnvVarKey(ConstrainedStr):
    regex = re.compile(r"[a-zA-Z]\w*")


# e.g. '5c833a78-1af3-43a7-9ed7-6a63b188f4d8'
class UUIDStr(ConstrainedStr):
    regex = re.compile(UUID_RE)


# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""
class IDStr(ConstrainedStr):
    strip_whitespace = True
    min_length = 1
    max_length = 100


class ShortTruncatedStr(ConstrainedStr):
    # NOTE: Use to input e.g. titles or display names
    # A truncated string:
    #   - Strips whitespaces and truncate strings that exceed the specified characters limit (curtail_length).
    #   - Ensures that the **input** data length to the API is controlled and prevents exceeding large inputs silently, i.e. without raising errors.
    # SEE https://github.com/ITISFoundation/osparc-simcore/pull/5989#discussion_r1650506583
    strip_whitespace = True
    curtail_length = 600


class LongTruncatedStr(ConstrainedStr):
    # NOTE: Use to input e.g. descriptions or summaries
    # Analogous to ShortTruncatedStr
    strip_whitespace = True
    curtail_length = 65536  # same as github descripton


# auto-incremented primary-key IDs
IdInt: TypeAlias = PositiveInt
PrimaryKeyInt: TypeAlias = PositiveInt


# https e.g. https://techterms.com/definition/https
class HttpSecureUrl(HttpUrl):
    allowed_schemes = {"https"}


class HttpUrlWithCustomMinLength(HttpUrl):
    # Overwriting min length to be back compatible when generating OAS
    min_length = 0


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
    DEBUG = "debug"
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
