""" Handlers for CRUD operations on /projects/{*}/nodes/{*}

"""

import logging
from typing import Any, Iterator

from aiohttp import web
from models_library.projects_nodes import Node, NodeID
from pydantic import BaseModel, parse_obj_as
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.json_serialization import json_dumps

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security_decorators import permission_required
from . import _ports, projects_api
from .project_models import ProjectDict
from .projects_db import ProjectDBAPI
from .projects_handlers_crud import ProjectPathParams, RequestContext

log = logging.getLogger(__name__)

#
# projects/*/inputs COLLECTION -------------------------
#

routes = web.RouteTableDef()


class ProjectPort(BaseModel):
    key: NodeID
    value: Any


class ProjectPortGet(ProjectPort):
    label: str


class ProjectPortsReplace(BaseModel):
    __root__: list[ProjectPort]

    def items(self) -> Iterator[tuple[NodeID, Any]]:
        return ((p.key, p.value) for p in self.__root__)


@routes.post(f"/{VTAG}/projects/{{project_id}}/inputs")
@login_required
@permission_required("project.read")
async def get_project_inputs(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    project: ProjectDict = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_templates=False,
        include_state=False,
    )

    workbench = parse_obj_as(dict[NodeID, Node], project["workbench"])
    inputs: dict[NodeID, Any] = _ports.get_project_inputs(workbench)

    return web.json_response(
        {
            "data": {
                node_id: ProjectPortGet(
                    key=node_id, label=workbench[node_id].label, value=value
                ).dict()
                for node_id, value in inputs.items()
            }
        },
        dumps=json_dumps,
    )


@routes.put(f"/{VTAG}/projects/{{project_id}}/inputs")
@login_required
@permission_required("project.update")
async def replace_project_inputs(request: web.Request) -> web.Response:
    app_db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    set_inputs = await parse_request_body_as(ProjectPortsReplace, request)

    project: ProjectDict = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_templates=False,
        include_state=False,
    )

    workbench = parse_obj_as(dict[NodeID, Node], project["workbench"])
    current_inputs: dict[NodeID, Any] = _ports.get_project_inputs(workbench)

    partial_workbench_data = {}

    for node_id, value in set_inputs.items():
        if node_id not in current_inputs.keys():
            raise web.HTTPBadRequest(reason=f"Invalid input key [{node_id}]")
        workbench[node_id].outputs = {"out_1": value}
        partial_workbench_data[node_id] = workbench[node_id].dict(
            include={"outputs"}, exclude_unset=True
        )

    assert app_db  # nosec
    updated_project, _ = await app_db.patch_user_project_workbench(
        partial_workbench_data, req_ctx.user_id, f"{path_params.project_id}"
    )

    workbench = parse_obj_as(dict[NodeID, Node], updated_project["workbench"])
    inputs: dict[NodeID, Any] = _ports.get_project_inputs(workbench)

    return web.json_response(
        {
            "data": {
                node_id: ProjectPortGet(
                    key=node_id, label=workbench[node_id].label, value=value
                ).dict()
                for node_id, value in inputs.items()
            }
        },
        dumps=json_dumps,
    )


#
# projects/*/outputs COLLECTION -------------------------
#


@routes.post(f"/{VTAG}/projects/{{project_id}}/outputs")
@login_required
@permission_required("project.read")
async def get_project_outputs(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    project: ProjectDict = await projects_api.get_project_for_user(
        request.app,
        project_uuid=f"{path_params.project_id}",
        user_id=req_ctx.user_id,
        include_templates=False,
        include_state=False,
    )

    workbench = parse_obj_as(dict[NodeID, Node], project["workbench"])
    outputs: dict[NodeID, Any] = _ports.get_project_outputs(workbench)

    return web.json_response(
        {
            "data": {
                node_id: ProjectPortGet(
                    key=node_id, label=workbench[node_id].label, value=value
                ).dict()
                for node_id, value in outputs.items()
            }
        },
        dumps=json_dumps,
    )
