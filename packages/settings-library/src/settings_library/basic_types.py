from enum import Enum
from typing import Annotated

from common_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from pydantic import BeforeValidator, Field, StringConstraints

from .utils_validators import validate_no_protocol_scheme

assert issubclass(LogLevel, Enum)  # nosec
assert issubclass(BootModeEnum, Enum)  # nosec
assert issubclass(BuildTargetEnum, Enum)  # nosec

__all__: tuple[str, ...] = (
    "BootModeEnum",
    "BuildTargetEnum",
    "LogLevel",
)


# port number range
type PortInt = Annotated[int, Field(gt=0, lt=65535)]
type RegisteredPortInt = Annotated[int, Field(gt=1024, lt=65535)]


# e.g. 'v5'
type VersionTag = Annotated[str, StringConstraints(pattern=r"^v\d$")]


# host with optional port, no protocol: "registry.example.com", "127.0.0.1:5000"
type HostNamePortStr = Annotated[str, BeforeValidator(validate_no_protocol_scheme)]


# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""
type IDStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
