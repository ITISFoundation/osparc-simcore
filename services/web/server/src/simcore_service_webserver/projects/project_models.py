from enum import Enum
from typing import Optional

from simcore_postgres_database.models.projects import ProjectType


class ProjectTypeAPI(str, Enum):
    all = "all"
    template = "template"
    user = "user"

    @classmethod
    def to_project_type_db(cls, api_type: "ProjectTypeAPI") -> Optional[ProjectType]:
        if api_type == ProjectTypeAPI.all:
            return None
        return (
            ProjectType.TEMPLATE
            if api_type == ProjectTypeAPI.template
            else ProjectType.STANDARD
        )
