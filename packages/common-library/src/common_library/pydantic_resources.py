from typing import Annotated, Any, Final

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

_NANO_CPUS_PER_CORE: Final[int] = 10**9


class CpuCores(BaseModel):
    """Amount of CPU cores allocated to a workload (e.g. a container).

    0 is excluded since several backends interpret it as "unlimited", which would
    silently disagree with any code accounting for the workload's cost.
    Use TotalCpuCores when 0 must be allowed (e.g. sums over zero workloads).
    """

    cores: Annotated[float, Field(gt=0)]

    model_config = ConfigDict(
        frozen=True,
        # settings arrive via pydantic-settings from env vars, e.g. DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT=0.1
        populate_by_name=True,
        validate_by_alias=True,
        validate_by_name=True,
        json_schema_extra={
            "examples": [
                # plain scalars are accepted, e.g. as parsed from env vars
                0.1,
                {"cores": 0.5},
            ]
        },
    )

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
        return int(self.cores * _NANO_CPUS_PER_CORE)

    def __str__(self) -> str:
        return f"{self.cores}"


class TotalCpuCores(CpuCores):
    """Same unit, for sums over a set of containers, where 0 means "no containers"."""

    cores: Annotated[float, Field(ge=0)]

    model_config = ConfigDict(
        json_schema_extra={"examples": [0, 0.4, {"cores": 2.0}]},
    )
