from typing import TypeAlias

from pydantic import BaseModel, Field, PositiveFloat

from ..projects_nodes_io import NodeID


class Stats(BaseModel):
    cpuUsage: PositiveFloat
    memUsage: PositiveFloat


class Limits(BaseModel):
    cpus: PositiveFloat
    mem: PositiveFloat


class Activity(BaseModel):
    stats: Stats
    limits: Limits
    queued: bool = Field(None)  # TODO: review since it in NOT filled


ActivityStatusDict: TypeAlias = dict[NodeID, Activity]
