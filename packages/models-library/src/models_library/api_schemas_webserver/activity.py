from typing import TypeAlias

from pydantic import BaseModel, PositiveFloat

from ..projects_nodes_io import NodeID


class Stats(BaseModel):
    cpuUsage: PositiveFloat
    memoryUsage: PositiveFloat


class Limits(BaseModel):
    cpus: PositiveFloat
    mem: PositiveFloat


class Activity(BaseModel):
    stats: Stats
    limits: Limits
    queued: bool


ActivityStatusDict: TypeAlias = dict[NodeID, Activity]
