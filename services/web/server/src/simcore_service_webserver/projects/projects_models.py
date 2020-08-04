"""
    Facade
"""

from typing import Optional

from pydantic import BaseModel

from simcore_postgres_database.webserver_models import ProjectType, projects


class Owner(BaseModel):
    first_name: str
    last_name: str


class ProjectLocked(BaseModel):
    value: bool
    owner: Optional[Owner]


class ProjectState(BaseModel):
    locked: ProjectLocked


__all__ = [
    "projects",
    "ProjectType",
    "ProjectState",
    "ProjectLocked",
    "Owner",
]
