from typing import Annotated, Any, TypeAlias

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
    field_validator,
    model_validator,
)
from pydantic.networks import AnyUrl
from pydantic.types import ByteSize, PositiveFloat

from ..generics import DictModel


class TaskCounts(BaseModel):
    error: int = 0
    memory: int = 0
    executing: int = 0


class WorkerMetrics(BaseModel):
    cpu: float = Field(..., description="consumed % of cpus")
    memory: ByteSize = Field(..., description="consumed memory")
    num_fds: int = Field(..., description="consumed file descriptors")
    task_counts: TaskCounts = Field(..., description="task details")


AvailableResources: TypeAlias = DictModel[str, PositiveFloat]


class UsedResources(DictModel[str, NonNegativeFloat]):
    @model_validator(mode="before")
    @classmethod
    def ensure_negative_value_is_zero(cls, values: dict[str, Any]):
        # dasks adds/remove resource values and sometimes
        # they end up being negative instead of 0
        for res_key, res_value in values.items():
            if res_value < 0:
                values[res_key] = 0
        return values


class Worker(BaseModel):
    id: str
    name: str
    resources: AvailableResources
    used_resources: UsedResources
    memory_limit: ByteSize
    metrics: WorkerMetrics


WorkersDict: TypeAlias = dict[AnyUrl, Worker]


class Scheduler(BaseModel):
    status: str = Field(..., description="The running status of the scheduler")
    workers: Annotated[WorkersDict | None, Field(default_factory=dict)]

    @field_validator("workers", mode="before")
    @classmethod
    def ensure_workers_is_empty_dict(cls, v):
        if v is None:
            return {}
        return v


class ClusterDetails(BaseModel):
    scheduler: Scheduler = Field(
        ...,
        description="This contains dask scheduler information given by the underlying dask library",
    )
    dashboard_link: AnyUrl = Field(
        ..., description="Link to this scheduler's dashboard"
    )
