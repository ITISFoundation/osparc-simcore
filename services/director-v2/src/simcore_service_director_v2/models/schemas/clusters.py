from models_library.clusters import Cluster
from models_library.generics import DictModel
from pydantic import BaseModel
from pydantic.networks import AnyUrl
from pydantic.types import ByteSize, PositiveFloat


class Worker(BaseModel):
    id: str
    name: str
    resources: DictModel[str, PositiveFloat]
    memory_limit: ByteSize


class WorkersDict(DictModel[AnyUrl, Worker]):
    ...


class Scheduler(BaseModel):
    status: str
    type: str
    workers: WorkersDict


class ClusterOut(BaseModel):
    scheduler: Scheduler
    cluster: Cluster
