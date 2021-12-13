from enum import Enum
from typing import Optional

from simcore_postgres_database.models.projects import ProjectType


class ProjectTypeAPI(str, Enum):
    all = "all"
    template = "template"
    user = "user"

    @classmethod
    def to_project_type_db(cls, api_type: "ProjectTypeAPI") -> Optional[ProjectType]:
        return {
            ProjectTypeAPI.all: None,
            ProjectTypeAPI.template: ProjectType.TEMPLATE,
            ProjectTypeAPI.user: ProjectType.STANDARD,
        }[api_type]
