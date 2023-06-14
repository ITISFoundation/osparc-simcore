from enum import Enum
from typing import Any, TypeAlias

from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.projects import ProjectType

ProjectDict: TypeAlias = dict[str, Any]
ProjectProxy: TypeAlias = RowProxy


class ProjectTypeAPI(str, Enum):
    all = "all"
    template = "template"
    user = "user"

    @classmethod
    def to_project_type_db(cls, api_type: "ProjectTypeAPI") -> ProjectType | None:
        return {
            ProjectTypeAPI.all: None,
            ProjectTypeAPI.template: ProjectType.TEMPLATE,
            ProjectTypeAPI.user: ProjectType.STANDARD,
        }[api_type]


__all__: tuple[str, ...] = (
    "ProjectDict",
    "ProjectProxy",
)
