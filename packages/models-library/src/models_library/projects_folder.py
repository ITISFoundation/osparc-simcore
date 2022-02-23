"""
    Models Project with Folder
"""

from typing import Optional

from pydantic import Extra

from .projects import Project


class ProjectWithFolder(Project):
    folder: Optional[int] = None

    class Config:
        extra = Extra.forbid
