from enum import Enum
from typing import Annotated, Any, Final

from common_library.basic_types import BootModeEnum, BuildTargetEnum, LogLevel
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_serializer,
    model_validator,
)

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


_NANO_CPUS_PER_CORE: Final[int] = 10**9


class CpuCores(BaseModel):
    """CPU cores allocated to a container.

    0 is excluded: docker interprets it as "unlimited", which would silently
    disagree with any code accounting for a container's cost.
    """

    cores: Annotated[float, Field(gt=0)]

    model_config = ConfigDict(frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _accept_plain_number(cls, value: Any) -> Any:
        # settings arrive from env vars as scalars, e.g. DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT=0.1
        if isinstance(value, int | float | str):
            return {"cores": value}
        return value

    @model_serializer
    def _serialize_as_number(self) -> float:
        # keeps env-var/JSON round-trips scalar, e.g. {"..._CPU_LIMIT": 0.1}
        return self.cores

    def to_nano_cpus(self) -> int:
        """the docker API expresses a CPU quota as NanoCPUs; labels and compose `cpus` stay in cores"""
        return int(self.cores * _NANO_CPUS_PER_CORE)

    def __str__(self) -> str:
        return f"{self.cores}"


class TotalCpuCores(CpuCores):
    """Same unit, for sums over a set of containers, where 0 means "no containers"."""

    cores: Annotated[float, Field(ge=0)]


# e.g. 'v5'
type VersionTag = Annotated[str, StringConstraints(pattern=r"^v\d$")]


# non-empty bounded string used as identifier
# e.g. "123" or "name_123" or "fa327c73-52d8-462a-9267-84eeaf0f90e3" but NOT ""
type IDStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
