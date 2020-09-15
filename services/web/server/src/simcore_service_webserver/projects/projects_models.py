"""
    Facade
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel

from simcore_postgres_database.webserver_models import ProjectType, projects


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
    "projects",
    "ProjectType",
    "ProjectState",
    "ProjectRunningState",
    "ProjectLocked",
    "RunningState",
    "Owner",
]
