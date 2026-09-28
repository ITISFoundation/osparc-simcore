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
        # required by the settings models embedding this type
        # (asserted by settings-library tests/test__models_examples.py)
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
        # CpuCores is a nested model, so pydantic accepts dicts only by default;
        # the deployed wire format however is a scalar everywhere: env vars parsed
        # by pydantic-settings (DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT=0.1) and JSON blobs
        # director-v2 hands to the dynamic-sidecar (see _serialize_as_number).
        # Without this, every existing scalar configuration would fail validation.
        if isinstance(value, int | float | str):
            return {"cores": value}
        return value

    @model_serializer
    def _serialize_as_number(self) -> float:
        # by default pydantic serializes a model as its fields ({"cores": 0.1});
        # overriding keeps the scalar format these settings had as plain floats,
        # e.g. {"DYNAMIC_SIDECAR_ENVOY_CPU_LIMIT": 0.1}. Required for rolling
        # deployments: director-v2 dumps these settings into env vars
        # (model_dump_json) that older dynamic-sidecar images parse as scalars.
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
