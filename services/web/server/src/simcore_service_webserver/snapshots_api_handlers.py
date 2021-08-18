import logging
from datetime import datetime
from functools import wraps
from typing import Any, Awaitable, Callable, List, Optional
from uuid import UUID

import orjson
from aiohttp import web
from pydantic.decorator import validate_arguments
from pydantic.error_wrappers import ValidationError
from pydantic.main import BaseModel
from yarl import URL

from ._meta import api_version_prefix as vtag
from .constants import RQ_PRODUCT_KEY, RQT_USERID_KEY
from .login.decorators import login_required
from .projects import projects_api
from .projects.projects_exceptions import ProjectNotFoundError
from .security_decorators import permission_required
from .snapshots_core import ProjectDict, take_snapshot
from .snapshots_db import ProjectsRepository, SnapshotsRepository
from .snapshots_models import Snapshot, SnapshotItem

logger = logging.getLogger(__name__)


def _default(obj):
    if isinstance(obj, BaseModel):
        return obj.dict()
    raise TypeError


def json_dumps(v) -> str:
    # orjson.dumps returns bytes, to match standard json.dumps we need to decode
    return orjson.dumps(v, default=_default).decode()


def enveloped_response(data: Any, **extra) -> web.Response:
    enveloped: str = json_dumps({"data": data, **extra})
    return web.Response(text=enveloped, content_type="application/json")


def handle_request_errors(handler: Callable[[web.Request], Awaitable[web.Response]]):
    """
    - required and type validation of path and query parameters
    """

    @wraps(handler)
    async def wrapped(request: web.Request):
        try:
            resp = await handler(request)
            return resp

        except KeyError as err:
            # NOTE: handles required request.match_info[*] or request.query[*]
            logger.debug(err, exc_info=True)
            raise web.HTTPBadRequest(reason=f"Expected parameter {err}") from err

        except ValidationError as err:
            #  NOTE: pydantic.validate_arguments parses and validates -> ValidationError
            logger.debug(err, exc_info=True)
            raise web.HTTPUnprocessableEntity(
                text=json_dumps({"error": err.errors()}),
                content_type="application/json",
            ) from err

        except ProjectNotFoundError as err:
            logger.debug(err, exc_info=True)
            raise web.HTTPNotFound(
                reason=f"Project not found {err.project_uuid} or not accessible. Skipping snapshot"
            ) from err

    return wrapped


def create_url_for_function(request: web.Request) -> Callable:
    app = request.app

    def url_for(router_name: str, **params) -> Optional[str]:
        try:
            rel_url: URL = app.router[router_name].url_for(
                **{k: str(v) for k, v in params.items()}
            )
            url = request.url.origin().with_path(str(rel_url))
            return str(url)
        except KeyError:
            return None

    return url_for


# FIXME: access rights using same approach as in access_layer.py in storage.
# A user can only check snapshots (subresource) of its project (parent resource)


# API ROUTES HANDLERS ---------------------------------------------------------
routes = web.RouteTableDef()


@routes.get(
    f"/{vtag}/projects/{{project_id}}/snapshots",
    name="list_project_snapshots_handler",
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def list_project_snapshots_handler(request: web.Request):
    """
    Lists references on project snapshots
    """
    snapshots_repo = SnapshotsRepository(request)
    url_for = create_url_for_function(request)

    @validate_arguments
    async def _list_snapshots(project_id: UUID) -> List[Snapshot]:
        # project_id is param-project?
        # TODO: add pagination
        # TODO: optimizaiton will grow snapshots of a project with time!
        #
        snapshots_orm = await snapshots_repo.list_all(project_id)
        # snapshots:
        #   - ordered (iterations!)
        #   - have a parent project with all the parametrization

        return [Snapshot.from_orm(obj) for obj in snapshots_orm]

    snapshots: List[Snapshot] = await _list_snapshots(
        project_id=request.match_info["project_id"],  # type: ignore
    )
    # TODO: async for snapshot in await list_snapshot is the same?

    data = [SnapshotItem.from_snapshot(snp, url_for) for snp in snapshots]
    return enveloped_response(data)


@routes.get(
    f"/{vtag}/projects/{{project_id}}/snapshots/{{snapshot_id}}",
    name="get_project_snapshot_handler",
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def get_project_snapshot_handler(request: web.Request):
    snapshots_repo = SnapshotsRepository(request)
    url_for = create_url_for_function(request)

    @validate_arguments
    async def _get_snapshot(project_id: UUID, snapshot_id: str) -> Snapshot:
        snapshot_orm = await snapshots_repo.get_by_id(project_id, int(snapshot_id))

        if not snapshot_orm:
            raise web.HTTPNotFound(
                reason=f"snapshot {snapshot_id} for project {project_id} not found"
            )

        return Snapshot.from_orm(snapshot_orm)

    snapshot = await _get_snapshot(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_id=request.match_info["snapshot_id"],
    )

    data = SnapshotItem.from_snapshot(snapshot, url_for)
    return enveloped_response(data)


@routes.post(
    f"/{vtag}/projects/{{project_id}}/snapshots", name="create_project_snapshot_handler"
)
@login_required
@permission_required("project.create")
@handle_request_errors
async def create_project_snapshot_handler(request: web.Request):
    snapshots_repo = SnapshotsRepository(request)
    projects_repo = ProjectsRepository(request)
    user_id = request[RQT_USERID_KEY]
    url_for = create_url_for_function(request)

    @validate_arguments
    async def _create_snapshot(
        project_id: UUID,
        snapshot_label: Optional[str] = None,
    ) -> Snapshot:

        # fetch parent's project
        parent: ProjectDict = await projects_api.get_project_for_user(
            request.app,
            str(project_id),
            user_id,
            include_templates=False,
            include_state=False,
        )

        # fetch snapshot if any
        parent_uuid: UUID = UUID(parent["uuid"])
        snapshot_timestamp: datetime = parent["lastChangeDate"]

        snapshot_orm = await snapshots_repo.get(
            parent_uuid=parent_uuid, created_at=snapshot_timestamp
        )

        # FIXME: if exists but different name?

        if not snapshot_orm:
            # take a snapshot of the parent project and commit to db
            project: ProjectDict
            snapshot: Snapshot
            project, snapshot = await take_snapshot(
                parent,
                snapshot_label=snapshot_label,
            )

            # FIXME: Atomic?? project and snapshot shall be created in the same transaction!!
            # FIXME: project returned might already exist, then return same snaphot
            await projects_repo.create(project)
            snapshot_orm = await snapshots_repo.create(snapshot)

        return Snapshot.from_orm(snapshot_orm)

    snapshot = await _create_snapshot(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_label=request.query.get("snapshot_label"),
    )

    data = SnapshotItem.from_snapshot(snapshot, url_for)
    return enveloped_response(data)


@routes.get(
    f"/{vtag}/projects/{{project_id}}/snapshots/{{snapshot_id}}/parameters",
    name="get_snapshot_parameters_handler",
)
@login_required
@permission_required("project.read")
@handle_request_errors
async def get_project_snapshot_parameters_handler(
    request: web.Request,
):
    # pylint: disable=unused-variable
    # pylint: disable=unused-argument
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    @validate_arguments
    async def get_snapshot_parameters(
        project_id: UUID,
        snapshot_id: str,
    ):
        return {"x": 4, "y": "yes"}

    params = await get_snapshot_parameters(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_id=request.match_info["snapshot_id"],
    )

    return params
