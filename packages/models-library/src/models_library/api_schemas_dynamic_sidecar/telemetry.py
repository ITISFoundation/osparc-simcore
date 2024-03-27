from abc import abstractmethod
from pathlib import Path
from typing import Protocol

from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel, ByteSize, Field


class SDiskUsageProtocol(Protocol):
    @property
    @abstractmethod
    def total(self) -> int: ...

    @property
    @abstractmethod
    def used(self) -> int: ...

    @property
    @abstractmethod
    def free(self) -> int: ...

    @property
    @abstractmethod
    def percent(self) -> float: ...


class DiskUsage(BaseModel):
    used: ByteSize = Field(description="used space")
    free: ByteSize = Field(description="remaining space")

    total: ByteSize = Field(description="total space = free + used")
    used_percent: float = Field(
        gte=0.00,
        lte=100.00,
        description="Percent of used space relative to the total space",
    )

    @classmethod
    def from_ps_util_disk_usage(
        cls, ps_util_disk_usage: SDiskUsageProtocol
    ) -> "DiskUsage":
        total = ps_util_disk_usage.free + ps_util_disk_usage.used
        used_percent = round(ps_util_disk_usage.used * 100 / total, 2)
        return cls(
            used=ByteSize(ps_util_disk_usage.used),
            free=ByteSize(ps_util_disk_usage.free),
            total=ByteSize(total),
            used_percent=used_percent,
        )


class ServiceDiskUsage(BaseModel):
    node_id: NodeID
    usage: dict[Path, DiskUsage]
