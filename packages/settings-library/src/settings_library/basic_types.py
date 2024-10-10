#
# NOTE: This file copies some of the types from models_library.basic_types
#       This is a minor evil to avoid the maintenance burden that creates
#       an extra dependency to a larger models_library (intra-repo library)

from enum import Enum
from typing import Annotated, TypeAlias

from pydantic import Field, StringConstraints

# port number range
PortInt: TypeAlias = Annotated[int, Field(gt=0, lt=65535)]


# e.g. 'v5'
VersionTag: TypeAlias = Annotated[str, StringConstraints(pattern=r"^v\d$")]


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
    DEBUG = "debug"
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


# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""


IDStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
# TODO: add test to check that this `IDStr("blahh")` runs a validator or not
# TODO: try using constraingstring


# https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers#Registered_ports
RegisteredPortInt: TypeAlias = Annotated[int, Field(gt=1024, lt=65535)]
# TODO: figure out why this is defined twice
# TODO: add test to check that this `RegisteredPortInt(0)` fails
