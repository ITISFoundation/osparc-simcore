import logging
from typing import List

from aiohttp import web
from servicelib.rest_pagination_utils import PageResponseLimitOffset
from simcore_service_webserver.rest_utils import RESPONSE_MODEL_POLICY

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
    update_checkpoint_safe,
)
from .meta_db import VersionControlRepository
from .meta_models_repos import (
    Checkpoint,
    CheckpointAnnotations,
    CheckpointNew,
    Repo,
    WorkbenchView,
)
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
    limit = int(request.query.get("limit", 20))
    offset = int(request.query.get("offset", 0))

    vc_repo = VersionControlRepository(request)
    repos_rows, total_number_of_repos = await vc_repo.list_repos(offset, limit)

    # parse and validate
    data = [
        Repo.parse_obj(
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
        data=data,
        request_url=request.url,
        total=total_number_of_repos,
        limit=limit,
        offset=offset,
    ).dict(**RESPONSE_MODEL_POLICY)


@routes.post(f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints")
@login_required
@permission_required("project.create")
@handle_request_errors
async def _create_checkpoint_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    project_uuid = request.match_info["project_uuid"]

    body = CheckpointNew.parse_obj(await request.json())

    checkpoint: Checkpoint = await create_checkpoint_safe(
        request.app,
        user_id=user_id,
        project_uuid=project_uuid,  # type: ignore
        **body.dict(include={"tag", "message", "new_branch"}),
    )

    data = {
        "url": url_for(
            f"{__name__}._get_checkpoint_handler",
            project_uuid=project_uuid,
            ref_id=checkpoint.id,
        ),
        **checkpoint.dict(),
    }
    return enveloped_response(data, status_cls=web.HTTPCreated)


@routes.get(f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints")
@login_required
@permission_required("project.read")
@handle_request_errors
async def _list_checkpoints_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    project_uuid = request.match_info["project_uuid"]
    limit = int(request.query.get("limit", 20))
    offset = int(request.query.get("offset", 0))

    checkpoints: List[Checkpoint]

    checkpoints, total = await list_checkpoints_safe(
        app=request.app,
        project_uuid=project_uuid,  # type: ignore
        user_id=user_id,
        limit=limit,
        offset=offset,
    )

    data = [
        {
            "url": url_for(
                f"{__name__}._get_checkpoint_handler",
                project_uuid=project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(),
        }
        for checkpoint in checkpoints
    ]

    return PageResponseLimitOffset.paginate_data(
        data=data,
        request_url=request.url,
        total=total,
        limit=limit or total,
        offset=offset,
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
    project_uuid = request.match_info["project_uuid"]

    checkpoint: Checkpoint = await get_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=project_uuid,  # type: ignore
        ref_id=request.match_info["ref_id"],
    )

    data = {
        "url": url_for(
            f"{__name__}._get_checkpoint_handler",
            project_uuid=project_uuid,
            ref_id=checkpoint.id,
        ),
        **checkpoint.dict(),
    }
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
    project_uuid = request.match_info["project_uuid"]

    body = CheckpointAnnotations.parse_obj(await request.json())

    checkpoint: Checkpoint = await update_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=project_uuid,  # type: ignore
        ref_id=request.match_info["ref_id"],
        **body.dict(include={"tag", "message"}),
    )

    data = {
        "url": url_for(
            f"{__name__}._get_checkpoint_handler",
            project_uuid=project_uuid,
            ref_id=checkpoint.id,
        ),
        **checkpoint.dict(),
    }
    return enveloped_response(data)


@routes.post(f"/{vtag}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}:checkout")
@login_required
@permission_required("project.create")
@handle_request_errors
async def _checkout_handler(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    project_uuid = request.match_info["project_uuid"]

    checkpoint: Checkpoint = await checkout_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=project_uuid,  # type: ignore
        ref_id=request.match_info["ref_id"],
    )

    data = {
        "url": url_for(
            f"{__name__}._get_checkpoint_handler",
            project_uuid=project_uuid,
            ref_id=checkpoint.id,
        ),
        **checkpoint.dict(),
    }
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
    project_uuid = request.match_info["project_uuid"]

    checkpoint: Checkpoint = await get_checkpoint_safe(
        app=request.app,
        user_id=user_id,
        project_uuid=project_uuid,  # type: ignore
        ref_id=request.match_info["ref_id"],
    )

    view: WorkbenchView = await get_workbench(
        app=request.app,
        user_id=user_id,
        project_uuid=project_uuid,  # type: ignore
        ref_id=checkpoint.id,
    )

    data = {
        "url": url_for(
            f"{__name__}._get_checkpoint_workbench_handler",
            project_uuid=project_uuid,
            ref_id=checkpoint.id,
        ),
        **view.dict(),
    }

    return enveloped_response(data)


# WARNING: changes in handlers naming will have an effect
# since they are in sync with operation_id  (checked in tests)
rename_routes_as_handler_function(routes, prefix=__name__)
logger.debug("Routes collected in  %s:\n %s", __name__, view_routes(routes))
