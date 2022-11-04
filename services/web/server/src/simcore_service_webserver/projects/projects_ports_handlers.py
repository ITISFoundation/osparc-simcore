""" Handlers for some CRUD operations for
    - /projects/{*}/inputs
    - /projects/{*}/outputs
"""

import logging
from typing import Any

from aiohttp import web
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, NodeID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import BaseModel, Field, parse_obj_as
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


def enveloped_json_response(data: Any):
    return web.json_response(
        {"data": jsonable_encoder(data)},
        dumps=json_dumps,
    )


async def _get_validated_workbench_model(
    app: web.Application, project_id: ProjectID, user_id: UserID
) -> dict[NodeID, Node]:

    # TODO: get directly unvalidated workbench
    project: ProjectDict = await projects_api.get_project_for_user(
        app,
        project_uuid=f"{project_id}",
        user_id=user_id,
        include_templates=False,
        include_state=False,
    )

    workbench = parse_obj_as(dict[NodeID, Node], project["workbench"])
    return workbench


#
# projects/*/inputs COLLECTION -------------------------
#

routes = web.RouteTableDef()


class ProjectPort(BaseModel):
    key: NodeID = Field(
        ...,
        description="Project port UID. It corresponds to the node ID of the associated parameter node",
    )
    value: Any = Field(..., description="Value assigned to this i/o port")


class ProjectPortGet(ProjectPort):
    label: str


@routes.get(f"/{VTAG}/projects/{{project_id}}/inputs", name="get_project_inputs")
@login_required
@permission_required("project.read")
async def get_project_inputs(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    assert request.app  # nosec

    workbench = await _get_validated_workbench_model(
        app=request.app, project_id=path_params.project_id, user_id=req_ctx.user_id
    )
    inputs: dict[NodeID, Any] = _ports.get_project_inputs(workbench)

    return enveloped_json_response(
        data={
            node_id: ProjectPortGet(
                key=node_id, label=workbench[node_id].label, value=value
            )
            for node_id, value in inputs.items()
        }
    )


@routes.put(f"/{VTAG}/projects/{{project_id}}/inputs", name="replace_project_inputs")
@login_required
@permission_required("project.update")
async def replace_project_inputs(request: web.Request) -> web.Response:
    app_db: ProjectDBAPI = ProjectDBAPI.get_from_app_context(request.app)
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)
    inputs_updates = await parse_request_body_as(list[ProjectPort], request)

    assert request.app  # nosec

    workbench = await _get_validated_workbench_model(
        app=request.app, project_id=path_params.project_id, user_id=req_ctx.user_id
    )
    current_inputs: dict[NodeID, Any] = _ports.get_project_inputs(workbench)

    partial_workbench_data = {}

    for input_update in inputs_updates:
        node_id = input_update.key
        if node_id not in current_inputs.keys():
            raise web.HTTPBadRequest(reason=f"Invalid input key [{node_id}]")

        workbench[node_id].outputs = {"out_1": input_update.value}
        partial_workbench_data[node_id] = workbench[node_id].dict(
            include={"outputs"}, exclude_unset=True
        )

    assert app_db  # nosec
    updated_project, _ = await app_db.patch_user_project_workbench(
        partial_workbench_data, req_ctx.user_id, f"{path_params.project_id}"
    )

    workbench = parse_obj_as(dict[NodeID, Node], updated_project["workbench"])
    inputs: dict[NodeID, Any] = _ports.get_project_inputs(workbench)

    return enveloped_json_response(
        data={
            node_id: ProjectPortGet(
                key=node_id, label=workbench[node_id].label, value=value
            )
            for node_id, value in inputs.items()
        }
    )


#
# projects/*/outputs COLLECTION -------------------------
#


@routes.get(f"/{VTAG}/projects/{{project_id}}/outputs", name="get_project_outputs")
@login_required
@permission_required("project.read")
async def get_project_outputs(request: web.Request) -> web.Response:
    req_ctx = RequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(ProjectPathParams, request)

    assert request.app  # nosec

    workbench = await _get_validated_workbench_model(
        app=request.app, project_id=path_params.project_id, user_id=req_ctx.user_id
    )
    outputs: dict[NodeID, Any] = _ports.get_project_outputs(workbench)

    # FIXME: resolve references in outputs before return!!

    return web.json_response(
        data={
            node_id: ProjectPortGet(
                key=node_id, label=workbench[node_id].label, value=value
            )
            for node_id, value in outputs.items()
        }
    )
