from enum import Enum
from typing import Annotated, TypeAlias

from common_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from pydantic import Field, StringConstraints

assert issubclass(LogLevel, Enum)  # nosec
assert issubclass(BootModeEnum, Enum)  # nosec
assert issubclass(BuildTargetEnum, Enum)  # nosec

__all__: tuple[str, ...] = (
    "LogLevel",
    "BootModeEnum",
    "BuildTargetEnum",
)


# port number range
PortInt: TypeAlias = Annotated[int, Field(gt=0, lt=65535)]
RegisteredPortInt: TypeAlias = Annotated[int, Field(gt=1024, lt=65535)]


# e.g. 'v5'
VersionTag: TypeAlias = Annotated[str, StringConstraints(pattern=r"^v\d$")]


# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""
IDStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
]
