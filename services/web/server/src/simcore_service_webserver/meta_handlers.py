""" web-api handler functions added by the meta app's module

"""
from typing import Any, Dict, List

from aiohttp import web
from models_library.projects import ProjectID
from pydantic import BaseModel

from ._meta import api_version_prefix as VTAG
from .version_control_models import CheckpointID


class ProjectIteration(BaseModel):
    id: int
    project_id: ProjectID
    checkpoint_id: CheckpointID
    parametrization: Dict[str, Any]


routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/meta/projects/{{project_id}}/iterations")
def list_meta_project_iterations(request: web.Request) -> web.Response:
    raise NotImplementedError


@routes.post(f"/{VTAG}/meta/projects/{{project_id}}/iterations")
def create_meta_project_iterations(request: web.Request) -> web.Response:
    # force-branch perh iteration but does not run it
    raise NotImplementedError


@routes.get(
    f"/{VTAG}/meta/projects/{{project_id}}/iterations/{{iteration_id}}/parametrization"
)
def get_iterations_parametrization(request: web.Request) -> web.Response:

    raise NotImplementedError
