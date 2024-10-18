from abc import abstractmethod
from enum import auto
from typing import Any, Final, Protocol

from pydantic import (
    BaseModel,
    ByteSize,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    root_validator,
    validator,
)

from ..projects_nodes_io import NodeID
from ..utils.enums import StrAutoEnum

_EPSILON: Final[NonNegativeFloat] = 1e-16


class MountPathCategory(StrAutoEnum):
    HOST = auto()
    STATES_VOLUMES = auto()
    INPUTS_VOLUMES = auto()
    OUTPUTS_VOLUMES = auto()


class SDiskUsageProtocol(Protocol):
    @property
    @abstractmethod
    def total(self) -> int:
        ...

    @property
    @abstractmethod
    def used(self) -> int:
        ...

    @property
    @abstractmethod
    def free(self) -> int:
        ...

    @property
    @abstractmethod
    def percent(self) -> float:
        ...


def _get_percent(used: float, total: float) -> float:
    return round(used * 100 / (total + _EPSILON), 2)


class DiskUsage(BaseModel):
    used: ByteSize = Field(description="used space")
    free: ByteSize = Field(description="remaining space")

    total: ByteSize = Field(description="total space = free + used")
    used_percent: NonNegativeFloat = Field(
        gte=0.00,
        lte=100.00,
        description="Percent of used space relative to the total space",
    )

    @validator("free")
    @classmethod
    def _free_positive(cls, v: float) -> float:
        if v < 0:
            msg = f"free={v} cannot be a negative value"
            raise ValueError(msg)
        return v

    @validator("used")
    @classmethod
    def _used_positive(cls, v: float) -> float:
        if v < 0:
            msg = f"used={v} cannot be a negative value"
            raise ValueError(msg)
        return v

    @root_validator(pre=True)
    @classmethod
    def _check_total(cls, values: dict[str, Any]) -> dict[str, Any]:
        total = values["total"]
        free = values["free"]
        used = values["used"]
        if total != free + used:
            msg = f"{total=} is different than the sum of {free=}+{used=} => sum={free+used}"
            raise ValueError(msg)
        return values

    @classmethod
    def from_efs_guardian(
        cls, used: NonNegativeInt, total: NonNegativeInt
    ) -> "DiskUsage":
        free = total - used
        return cls(
            used=ByteSize(used),
            free=ByteSize(free),
            total=ByteSize(total),
            used_percent=_get_percent(used, total),
        )

    @classmethod
    def from_ps_util_disk_usage(
        cls, ps_util_disk_usage: SDiskUsageProtocol
    ) -> "DiskUsage":
        total = ps_util_disk_usage.free + ps_util_disk_usage.used
        return cls.from_efs_guardian(ps_util_disk_usage.used, total)

    def __hash__(self):
        return hash((self.used, self.free, self.total, self.used_percent))


class ServiceDiskUsage(BaseModel):
    node_id: NodeID
    usage: dict[MountPathCategory, DiskUsage]
