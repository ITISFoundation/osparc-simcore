from pathlib import Path

from models_library.projects_nodes_io import NodeID
from pydantic import BaseModel, Field, NonNegativeInt


class DiskUsage(BaseModel):
    total: NonNegativeInt
    used: NonNegativeInt
    free: NonNegativeInt
    percent: float = Field(gte=0.0, lte=1.0)


class ServiceDiskUsage(BaseModel):
    node_id: NodeID
    usage: dict[Path, DiskUsage]
