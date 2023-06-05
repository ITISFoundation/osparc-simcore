import re
from enum import Enum
from typing import TypeAlias

from pydantic import ConstrainedInt, ConstrainedStr, HttpUrl, PositiveInt

from .basic_regex import UUID_RE, VERSION_RE


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
class SHA1Str(ConstrainedStr):
    regex = re.compile(r"^[a-fA-F0-9]{40}$")


class MD5Str(ConstrainedStr):
    regex = re.compile(r"^[a-fA-F0-9]{32}$")


# env var
class EnvVarKey(ConstrainedStr):
    regex = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*")


# e.g. '5c833a78-1af3-43a7-9ed7-6a63b188f4d8'
class UUIDStr(ConstrainedStr):
    regex = re.compile(UUID_RE)


# auto-incremented primary-key IDs
IdInt: TypeAlias = PositiveInt
PrimaryKeyInt: TypeAlias = PositiveInt


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
