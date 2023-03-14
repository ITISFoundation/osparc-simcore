import json
from enum import Enum
from typing import Any, Optional

from aiohttp import web
from aiopg.sa.result import RowProxy
from simcore_postgres_database.models.projects import ProjectType

from .._constants import APP_JSONSCHEMA_SPECS_KEY
from .._resources import resources

# TODO: extend
ProjectDict = dict[str, Any]
ProjectProxy = RowProxy


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


def setup_projects_model_schema(app: web.Application):
    # NOTE: inits once per app
    # FIXME: schemas are hard-coded to api/V0!!!
    with resources.stream("api/v0/schemas/project-v0.0.1-pydantic.json") as fh:
        project_schema = json.load(fh)

    if app.get(APP_JSONSCHEMA_SPECS_KEY) is None:
        app[APP_JSONSCHEMA_SPECS_KEY] = {"projects": project_schema}

    elif app[APP_JSONSCHEMA_SPECS_KEY].get("projects") is None:
        app[APP_JSONSCHEMA_SPECS_KEY]["projects"] = project_schema

    return app[APP_JSONSCHEMA_SPECS_KEY]["projects"]


__all__: tuple[str, ...] = (
    "ProjectDict",
    "ProjectProxy",
    "setup_projects_model_schema",
)
