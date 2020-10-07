from datetime import datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, HttpUrl, confloat

LATEST_VERSION = "latest"

class SolverRelease(BaseModel):
    name: Optional[str] = None
    version: str
    release_date: datetime


class SolverDescriptorBase(BaseModel):
    solver_id: UUID
    name: str
    maintainer: str


class SolverOverview(SolverDescriptorBase):
    latest_version: str
    solver_url: HttpUrl


class SolverDetailed(SolverDescriptorBase):
    releases: List[SolverRelease]


class RunProxy(BaseModel):
    run_id: UUID
    inputs_sha: str
    status_url: HttpUrl
    results_url: HttpUrl


# TODO: these need to be in sync with celery task states
class TaskStates(str, Enum):
    UNDEFINED = "undefined"
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class RunState(BaseModel):
    status: TaskStates = TaskStates.UNDEFINED
    progress: int = confloat(ge=0, le=100)
    started_at: datetime
    stopped_at: Union[datetime, None] = None


class SolverInput(BaseModel):
    name: str
    content_type: str
    key: Optional[str] = None
    value: Union[float, str, int, HttpUrl]
