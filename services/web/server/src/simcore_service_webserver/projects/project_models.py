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
    with resources.stream("api/v0/schemas/project-v0.0.1-pydantic.json") as fh:
        project_schema = json.load(fh)

        # WARNING: Mar.2023 During changing to pydantic generated json schema
        # found out there was BUG in the previously used project-v0.0.1.json schema
        # This is a temporary patch, until the bug is fixed.
        # https://github.com/ITISFoundation/osparc-simcore/issues/3992
        # Tested in test_validate_project_json_schema()
        project_schema["properties"]["workbench"].pop("patternProperties")
        project_schema["properties"]["ui"]["properties"]["workbench"].pop(
            "patternProperties"
        )

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
