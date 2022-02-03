from typing import Optional

from models_library.clusters import Cluster
from models_library.generics import DictModel
from pydantic import BaseModel, Field
from pydantic.networks import AnyUrl
from pydantic.types import ByteSize, PositiveFloat


class WorkerMetrics(BaseModel):
    cpu: float = Field(..., description="consumed # of cpus")
    memory: ByteSize = Field(..., description="consumed memory")
    num_fds: int = Field(..., description="consumed file descriptors")
    ready: int = Field(..., description="# tasks ready to run")
    executing: int = Field(..., description="# tasks currently executing")
    in_flight: int = Field(..., description="# tasks currenntly waiting for data")
    in_memory: ByteSize = Field(..., description="result data still in memory")


class Worker(BaseModel):
    id: str
    name: str
    resources: DictModel[str, PositiveFloat]
    memory_limit: ByteSize
    metrics: WorkerMetrics


class WorkersDict(DictModel[AnyUrl, Worker]):
    ...


class Scheduler(BaseModel):
    status: str
    type: str
    workers: WorkersDict


class ClusterOut(BaseModel):
    scheduler: Scheduler
    cluster: Cluster
    dashboard_link: Optional[AnyUrl] = None
