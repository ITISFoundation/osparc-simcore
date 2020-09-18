from enum import Enum
from typing import Optional

from pydantic import BaseModel


class Owner(BaseModel):
    first_name: str
    last_name: str


class ProjectLocked(BaseModel):
    value: bool
    owner: Optional[Owner]


class RunningState(str, Enum):
    not_started = "NOT_STARTED"
    pending = "PENDING"
    started = "STARTED"
    retrying = "RETRY"
    success = "SUCCESS"
    failure = "FAILURE"


class ProjectRunningState(BaseModel):
    value: RunningState


class ProjectState(BaseModel):
    locked: ProjectLocked
    state: ProjectRunningState


__all__ = [
    "ProjectState",
    "ProjectRunningState",
    "ProjectLocked",
    "RunningState",
    "Owner",
]
