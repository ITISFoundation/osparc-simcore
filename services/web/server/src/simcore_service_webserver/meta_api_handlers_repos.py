import logging
from typing import List

from aiohttp import web
from servicelib.rest_pagination_utils import PageResponseLimitOffset

from ._meta import api_version_prefix as vtag
from .constants import RQT_USERID_KEY
from .login.decorators import login_required
from .meta_api_handlers_base import (
    create_url_for_function,
    enveloped_response,
    handle_request_errors,
)
from .meta_core_repos import (
    checkout_checkpoint_safe,
    create_checkpoint_safe,
    get_checkpoint_safe,
    get_workbench,
    list_checkpoints_safe,
    list_repos,
    update_checkpoint_safe,
)
from .meta_db import VersionControlRepository
from .meta_models_repos import (
    Checkpoint,
    CheckpointAnnotations,
    CheckpointApiModel,
    CheckpointNew,
    RepoApiModel,
    WorkbenchView,
    WorkbenchViewApiModel,
)
from .rest_utils import RESPONSE_MODEL_POLICY
from .security_decorators import permission_required
from .utils_aiohttp import rename_routes_as_handler_function, view_routes

logger = logging.getLogger(__name__)


# FIXME: access rights using same approach as in access_layer.py in storage.
# A user can only check snapshots (subresource) of its project (parent resource)


# API ROUTES HANDLERS ---------------------------------------------------------
routes = web.RouteTableDef()


@routes.get(f"/{vtag}/repos/projects")
@login_required
@permission_required("project.read")
@handle_request_errors
async def _list_repos_handler(request: web.Request):
    # FIXME: check access to non owned projects user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _limit = int(request.query.get("limit", 20))
    _offset = int(request.query.get("offset", 0))

    repos_rows, total_number_of_repos = await list_repos(
        vc_repo, offset=_offset, limit=_limit
    )

    assert len(repos_rows) <= _limit  # nosec

    # parse and validate
    repos_list = [
        RepoApiModel.parse_obj(
            {
                "url": url_for(
                    f"{__name__}._list_checkpoints_handler",
                    project_uuid=row.project_uuid,
                ),
                **row.dict(),
            }
        )
        for row in repos_rows
    ]

    return PageResponseLimitOffset.paginate_data(
        data=repos_list,
        request_url=request.url,
        total=total_number_of_repos,
        limit=_limit,
        offset=_offset,
    ).dict(**RESPONSE_MODEL_POLICY)


@routes.post(f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints")
@login_required
@permission_required("project.create")
@handle_request_errors
async def _create_checkpoint_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    _project_uuid = request.match_info["project_uuid"]
    _body = CheckpointNew.parse_obj(await request.json())

    checkpoint: Checkpoint = await create_checkpoint_safe(
        request.app,
        user_id=user_id,
        project_uuid=_project_uuid,  # type: ignore
        **_body.dict(include={"tag", "message", "new_branch"}),
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                f"{__name__}._get_checkpoint_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(),
        }
    )
    return enveloped_response(data, status_cls=web.HTTPCreated)


@routes.get(f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints")
@login_required
@permission_required("project.read")
@handle_request_errors
async def _list_checkpoints_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    _project_uuid = request.match_info["project_uuid"]
    _limit = int(request.query.get("limit", 20))
    _offset = int(request.query.get("offset", 0))

    checkpoints: List[Checkpoint]

    checkpoints, total = await list_checkpoints_safe(
        app=request.app,
        project_uuid=_project_uuid,  # type: ignore
        user_id=user_id,
        limit=_limit,
        offset=_offset,
    )

    # parse and validate
    checkpoints_list = [
        CheckpointApiModel.parse_obj(
            {
                "url": url_for(
                    f"{__name__}._get_checkpoint_handler",
                    project_uuid=_project_uuid,
                    ref_id=checkpoint.id,
                ),
                **checkpoint.dict(),
            }
        )
        for checkpoint in checkpoints
    ]

    return PageResponseLimitOffset.paginate_data(
        data=checkpoints_list,
        request_url=request.url,
        total=total,
        limit=_limit or total,
        offset=_offset,
    ).dict(**RESPONSE_MODEL_POLICY)


@routes.get(
    f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}",
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def _get_checkpoint_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    _project_uuid = request.match_info["project_uuid"]
    _ref_id = request.match_info["ref_id"]

    checkpoint: Checkpoint = await get_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=_ref_id,
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                f"{__name__}._get_checkpoint_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(),
        }
    )
    return enveloped_response(data)


@routes.patch(
    f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}",
)
@login_required
@permission_required("project.update")
@handle_request_errors
async def _update_checkpoint_annotations_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    _project_uuid = request.match_info["project_uuid"]
    _ref_id = request.match_info["ref_id"]

    _body = CheckpointAnnotations.parse_obj(await request.json())

    checkpoint: Checkpoint = await update_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=_ref_id,
        **_body.dict(include={"tag", "message"}),
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                f"{__name__}._get_checkpoint_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(),
        }
    )
    return enveloped_response(data)


@routes.post(f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}:checkout")
@login_required
@permission_required("project.create")
@handle_request_errors
async def _checkout_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    _project_uuid = request.match_info["project_uuid"]
    _ref_id = request.match_info["ref_id"]

    checkpoint: Checkpoint = await checkout_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=_ref_id,
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                f"{__name__}._get_checkpoint_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(),
        }
    )
    return enveloped_response(data)


@routes.get(
    f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}/workbench/view"
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def _view_project_workbench_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    _project_uuid = request.match_info["project_uuid"]
    _ref_id = request.match_info["ref_id"]

    checkpoint: Checkpoint = await get_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=_ref_id,
    )

    view: WorkbenchView = await get_workbench(
        app=request.app,
        user_id=user_id,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=checkpoint.id,
    )

    data = WorkbenchViewApiModel.parse_obj(
        {
            "url": url_for(
                f"{__name__}._get_checkpoint_workbench_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            **view.dict(),
        }
    )

    return enveloped_response(data)


# WARNING: changes in handlers naming will have an effect
# since they are in sync with operation_id  (checked in tests)
rename_routes_as_handler_function(routes, prefix=__name__)
logger.debug("Routes collected in  %s:\n %s", __name__, view_routes(routes))
