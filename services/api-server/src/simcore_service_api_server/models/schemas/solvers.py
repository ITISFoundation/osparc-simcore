from datetime import datetime
from enum import Enum
from typing import List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, HttpUrl, confloat, constr

LATEST_VERSION = "latest"
KEY_RE = r"^(simcore)/(services)/(comp)(/[^\s/]+)+$"


# Human-readable unique identifier
KeyIdentifier = constr(strip_whitespace=True, min_length=3)
SolverKey = constr(regex=KEY_RE, strip_whitespace=True)


class SolverRelease(BaseModel):
    solver_id: UUID
    version: str
    version_alias: List[str] = [] # TODO: must be unique!
    release_date: datetime

class SolverBase(BaseModel):
    solver_key: SolverKey
    title: str
    maintainer: str


class SolverOverview(SolverBase):
    latest_version: str
    solver_url: HttpUrl


class Solver(SolverBase):
    releases: List[SolverRelease] # sorted from latest to oldest


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
    key: KeyIdentifier
    content_type: str
    title: Optional[str] = None


class RunInput(SolverInput):
    value: Union[float, str, int, None] = None
    value_url: Optional[HttpUrl] = None

    # TODO: validate one or the other but not both


class SolverOutput(BaseModel):
    content_type: str
    key: KeyIdentifier
    title: Optional[str] = None


class RunOutput(SolverOutput):
    status: TaskStates = TaskStates.UNDEFINED  # every output can
    value: Optional[Union[float, str, int]] = None
    value_url: Optional[HttpUrl] = None
