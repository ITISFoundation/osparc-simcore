import logging

from aiohttp import web
from models_library.projects import ProjectID
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.rest_pagination_utils import paginate_data
from pydantic import BaseModel, validator
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import api_version_prefix as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import create_url_for_function, envelope_json_response
from ._core import (
    checkout_checkpoint,
    create_checkpoint,
    get_checkpoint,
    get_workbench,
    list_checkpoints,
    list_repos,
    update_checkpoint,
)
from ._handlers_base import handle_request_errors
from .db import VersionControlRepository
from .models import (
    HEAD,
    Checkpoint,
    CheckpointAnnotations,
    CheckpointApiModel,
    CheckpointNew,
    RefID,
    RepoApiModel,
    WorkbenchView,
    WorkbenchViewApiModel,
)

_logger = logging.getLogger(__name__)


class _CheckpointsPathParam(BaseModel):
    project_uuid: ProjectID
    ref_id: RefID

    @validator("ref_id", pre=True)
    @classmethod
    def _normalize_refid(cls, v):
        if v and v == "HEAD":
            return HEAD
        return v


class _ProjectPathParam(BaseModel):
    project_uuid: ProjectID


routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/repos/projects", name="list_repos")
@login_required
@permission_required("project.read")
@handle_request_errors
async def _list_repos_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    query_params = parse_request_query_parameters_as(PageQueryParameters, request)

    repos_rows, total_number_of_repos = await list_repos(
        vc_repo, offset=query_params.offset, limit=query_params.limit
    )

    assert len(repos_rows) <= query_params.limit  # nosec

    # parse and validate
    repos_list = [
        RepoApiModel.parse_obj(
            {
                "url": url_for(
                    "list_repos",
                    project_uuid=row.project_uuid,
                ),
                **dict(row.items()),
            }
        )
        for row in repos_rows
    ]

    page = Page[RepoApiModel].parse_obj(
        paginate_data(
            chunk=repos_list,
            request_url=request.url,
            total=total_number_of_repos,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


@routes.post(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints", name="create_checkpoint"
)
@login_required
@permission_required("project.create")
@handle_request_errors
async def _create_checkpoint_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    path_params = parse_request_path_parameters_as(_ProjectPathParam, request)
    _body = CheckpointNew.parse_obj(await request.json())

    checkpoint: Checkpoint = await create_checkpoint(
        vc_repo,
        project_uuid=path_params.project_uuid,
        **_body.dict(include={"tag", "message"}),
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                "get_checkpoint",
                project_uuid=path_params.project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(),
        }
    )
    return envelope_json_response(data, status_cls=web.HTTPCreated)


@routes.get(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints", name="list_checkpoints"
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def _list_checkpoints_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    path_params = parse_request_path_parameters_as(_ProjectPathParam, request)
    query_params = parse_request_query_parameters_as(PageQueryParameters, request)

    checkpoints: list[Checkpoint]

    checkpoints, total = await list_checkpoints(
        vc_repo,
        project_uuid=path_params.project_uuid,
        offset=query_params.offset,
        limit=query_params.limit,
    )

    # parse and validate
    checkpoints_list = [
        CheckpointApiModel.parse_obj(
            {
                "url": url_for(
                    "get_checkpoint",
                    project_uuid=path_params.project_uuid,
                    ref_id=checkpoint.id,
                ),
                **checkpoint.dict(),
            }
        )
        for checkpoint in checkpoints
    ]

    page = Page[CheckpointApiModel].parse_obj(
        paginate_data(
            chunk=checkpoints_list,
            request_url=request.url,
            total=total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return web.Response(
        text=page.json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


@routes.get(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/HEAD",
    name="get_head_checkpoint",
)
async def _get_checkpoint_handler_head(request: web.Request):
    # NOTE: added a function so below the route can be named
    return await _get_checkpoint_handler(request)


@routes.get(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}",
    name="get_checkpoint",
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def _get_checkpoint_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    path_params = parse_request_path_parameters_as(_CheckpointsPathParam, request)

    checkpoint: Checkpoint = await get_checkpoint(
        vc_repo,
        project_uuid=path_params.project_uuid,
        ref_id=path_params.ref_id,
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                "get_checkpoint",
                project_uuid=path_params.project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(**RESPONSE_MODEL_POLICY),
        }
    )
    return envelope_json_response(data)


@routes.patch(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}",
    name="update_checkpoint",
)
@login_required
@permission_required("project.update")
@handle_request_errors
async def _update_checkpoint_annotations_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    path_params = parse_request_path_parameters_as(_CheckpointsPathParam, request)
    update = await parse_request_body_as(CheckpointAnnotations, request)

    checkpoint: Checkpoint = await update_checkpoint(
        vc_repo,
        project_uuid=path_params.project_uuid,
        ref_id=path_params.ref_id,
        **update.dict(include={"tag", "message"}, exclude_none=True),
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                "get_checkpoint",
                project_uuid=path_params.project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(**RESPONSE_MODEL_POLICY),
        }
    )
    return envelope_json_response(data)


@routes.post(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}:checkout",
    name="checkout",
)
@login_required
@permission_required("project.create")
@handle_request_errors
async def _checkout_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    path_params = parse_request_path_parameters_as(_CheckpointsPathParam, request)

    checkpoint: Checkpoint = await checkout_checkpoint(
        vc_repo,
        project_uuid=path_params.project_uuid,
        ref_id=path_params.ref_id,
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                "get_checkpoint",
                project_uuid=path_params.project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(**RESPONSE_MODEL_POLICY),
        }
    )
    return envelope_json_response(data)


@routes.get(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}/workbench/view",
    name="view_project_workbench",
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def _view_project_workbench_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    path_params = parse_request_path_parameters_as(_CheckpointsPathParam, request)

    checkpoint: Checkpoint = await get_checkpoint(
        vc_repo,
        project_uuid=path_params.project_uuid,
        ref_id=path_params.ref_id,
    )

    view: WorkbenchView = await get_workbench(
        vc_repo,
        project_uuid=path_params.project_uuid,
        ref_id=checkpoint.id,
    )

    data = WorkbenchViewApiModel.parse_obj(
        {
            # = request.url??
            "url": url_for(
                "view_project_workbench",
                project_uuid=path_params.project_uuid,
                ref_id=checkpoint.id,
            ),
            "checkpoint_url": url_for(
                "get_checkpoint",
                project_uuid=path_params.project_uuid,
                ref_id=checkpoint.id,
            ),
            **view.dict(**RESPONSE_MODEL_POLICY),
        }
    )

    return envelope_json_response(data)
