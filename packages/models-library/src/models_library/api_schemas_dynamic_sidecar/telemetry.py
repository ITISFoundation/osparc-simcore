from pathlib import Path

from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel, ByteSize, Field


class DiskUsage(BaseModel):
    total: ByteSize = Field(description="total space")
    used: ByteSize = Field(description="space used")
    free: ByteSize = Field(description="remaining space")
    percent: float = Field(
        gte=0.0,
        lte=1.0,
        description="Percent of used space relative to the total space",
    )


class ServiceDiskUsage(BaseModel):
    node_id: NodeID
    usage: dict[Path, DiskUsage]
