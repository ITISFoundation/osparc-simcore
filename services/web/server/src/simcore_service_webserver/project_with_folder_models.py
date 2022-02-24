"""
    Models Project with Folder
"""

from typing import Optional

from models_library.projects import Project
from pydantic import Extra


class ProjectWithFolder(Project):
    folder: Optional[int] = None

    class Config:
        extra = Extra.forbid
