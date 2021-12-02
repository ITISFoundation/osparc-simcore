import logging
from typing import List

from aiohttp import web
from pydantic.decorator import validate_arguments
from servicelib.rest_pagination_utils import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageResponseLimitOffset,
)

from ._meta import api_version_prefix as VTAG
from .login.decorators import login_required
from .rest_utils import RESPONSE_MODEL_POLICY
from .security_decorators import permission_required
from .utils_aiohttp import (
    create_url_for_function,
    envelope_json_response,
    get_routes_view,
    rename_routes_as_handler_function,
)
from .version_control_core import (
    checkout_checkpoint_safe,
    create_checkpoint_safe,
    get_checkpoint_safe,
    get_workbench_safe,
    list_checkpoints_safe,
    list_repos_safe,
    update_checkpoint_safe,
)
from .version_control_db import HEAD, VersionControlRepository
from .version_control_handlers_base import handle_request_errors
from .version_control_models import (
    Checkpoint,
    CheckpointAnnotations,
    CheckpointApiModel,
    CheckpointNew,
    RefID,
    RepoApiModel,
    WorkbenchView,
    WorkbenchViewApiModel,
)

logger = logging.getLogger(__name__)


# FIXME: access rights using same approach as in access_layer.py in storage.
# A user can only check snapshots (subresource) of its project (parent resource)


@validate_arguments
def _normalize_refid(ref_id: RefID) -> RefID:
    if ref_id == "HEAD":
        return HEAD
    return ref_id


# API ROUTES HANDLERS ---------------------------------------------------------
routes = web.RouteTableDef()


@routes.get(f"/{VTAG}/repos/projects")
@login_required
@permission_required("project.read")
@handle_request_errors
async def _list_repos_handler(request: web.Request):
    # FIXME: check access to non owned projects user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _limit = int(request.query.get("limit", DEFAULT_NUMBER_OF_ITEMS_PER_PAGE))
    _offset = int(request.query.get("offset", 0))

    repos_rows, total_number_of_repos = await list_repos_safe(
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
                **dict(row.items()),
            }
        )
        for row in repos_rows
    ]

    return web.Response(
        text=PageResponseLimitOffset.paginate_data(
            data=repos_list,
            request_url=request.url,
            total=total_number_of_repos,
            limit=_limit,
            offset=_offset,
        ).json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


@routes.post(f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints")
@login_required
@permission_required("project.create")
@handle_request_errors
async def _create_checkpoint_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _project_uuid = request.match_info["project_uuid"]
    _body = CheckpointNew.parse_obj(await request.json())

    checkpoint: Checkpoint = await create_checkpoint_safe(
        vc_repo,
        project_uuid=_project_uuid,  # type: ignore
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
    return envelope_json_response(data, status_cls=web.HTTPCreated)


@routes.get(f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints")
@login_required
@permission_required("project.read")
@handle_request_errors
async def _list_checkpoints_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _project_uuid = request.match_info["project_uuid"]
    _limit = int(request.query.get("limit", DEFAULT_NUMBER_OF_ITEMS_PER_PAGE))
    _offset = int(request.query.get("offset", 0))

    checkpoints: List[Checkpoint]

    checkpoints, total = await list_checkpoints_safe(
        vc_repo,
        project_uuid=_project_uuid,  # type: ignore
        offset=_offset,
        limit=_limit,
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

    return web.Response(
        text=PageResponseLimitOffset.paginate_data(
            data=checkpoints_list,
            request_url=request.url,
            total=total,
            limit=_limit or total,
            offset=_offset,
        ).json(**RESPONSE_MODEL_POLICY),
        content_type="application/json",
    )


@routes.get(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}",
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def _get_checkpoint_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _project_uuid = request.match_info["project_uuid"]
    _ref_id = _normalize_refid(request.match_info["ref_id"])

    checkpoint: Checkpoint = await get_checkpoint_safe(
        vc_repo,
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
            **checkpoint.dict(**RESPONSE_MODEL_POLICY),
        }
    )
    return envelope_json_response(data)


@routes.patch(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}",
)
@login_required
@permission_required("project.update")
@handle_request_errors
async def _update_checkpoint_annotations_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _project_uuid = request.match_info["project_uuid"]
    _ref_id = _normalize_refid(request.match_info["ref_id"])

    _body = CheckpointAnnotations.parse_obj(await request.json())

    checkpoint: Checkpoint = await update_checkpoint_safe(
        vc_repo,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=_ref_id,
        **_body.dict(include={"tag", "message"}, exclude_none=True),
    )

    data = CheckpointApiModel.parse_obj(
        {
            "url": url_for(
                f"{__name__}._get_checkpoint_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            **checkpoint.dict(**RESPONSE_MODEL_POLICY),
        }
    )
    return envelope_json_response(data)


@routes.post(f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}:checkout")
@login_required
@permission_required("project.create")
@handle_request_errors
async def _checkout_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _project_uuid = request.match_info["project_uuid"]
    _ref_id = _normalize_refid(request.match_info["ref_id"])

    checkpoint: Checkpoint = await checkout_checkpoint_safe(
        vc_repo,
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
            **checkpoint.dict(**RESPONSE_MODEL_POLICY),
        }
    )
    return envelope_json_response(data)


@routes.get(
    f"/{VTAG}/repos/projects/{{project_uuid}}/checkpoints/{{ref_id}}/workbench/view"
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def _view_project_workbench_handler(request: web.Request):
    url_for = create_url_for_function(request)
    vc_repo = VersionControlRepository(request)

    _project_uuid = request.match_info["project_uuid"]
    _ref_id = _normalize_refid(request.match_info["ref_id"])

    checkpoint: Checkpoint = await get_checkpoint_safe(
        vc_repo,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=_ref_id,
    )

    view: WorkbenchView = await get_workbench_safe(
        vc_repo,
        project_uuid=_project_uuid,  # type: ignore
        ref_id=checkpoint.id,
    )

    data = WorkbenchViewApiModel.parse_obj(
        {
            "url": url_for(
                f"{__name__}._view_project_workbench_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            "checkpoint_url": url_for(
                f"{__name__}._get_checkpoint_handler",
                project_uuid=_project_uuid,
                ref_id=checkpoint.id,
            ),
            **view.dict(**RESPONSE_MODEL_POLICY),
        }
    )

    return envelope_json_response(data)


# WARNING: changes in handlers naming will have an effect
# since they are in sync with operation_id  (checked in tests)
rename_routes_as_handler_function(routes, prefix=__name__)
logger.debug("Routes collected in  %s:\n %s", __name__, get_routes_view(routes))
