from enum import Enum
from typing import Any, Dict, Optional, Tuple

from aiopg.sa.result import ResultProxy
from simcore_postgres_database.models.projects import ProjectType

# TODO: extend
ProjectDict = Dict[str, Any]
ProjectProxy = ResultProxy


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


__all__: Tuple[str, ...] = ("ProjectDict", "ProjectProxy")
