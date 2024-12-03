from enum import StrEnum
from typing import Any

from pydantic_core import PydanticUndefined

# SEE https://github.com/fastapi/fastapi/blob/master/fastapi/_compat.py#L75-L78
Undefined = PydanticUndefined
UNSET: Any = Undefined
# Use `UNSET` as default when default_factory
# SEE https://github.com/ITISFoundation/osparc-simcore/pull/6882


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
