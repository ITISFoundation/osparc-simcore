import json
from functools import wraps
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from aiohttp import web
from models_library.projects import Project
from pydantic.decorator import validate_arguments
from pydantic.error_wrappers import ValidationError
from simcore_service_webserver.snapshots_models import Snapshot

from ._meta import api_version_prefix as vtag
from .constants import RQ_PRODUCT_KEY, RQT_USERID_KEY
from .snapshots_models import Snapshot, SnapshotApiModel

json_dumps = json.dumps


def handle_request_errors(handler: Callable):
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
            raise web.HTTPBadRequest(reason="Expected parameter {err}") from err

        except ValidationError as err:
            #  NOTE: pydantic.validate_arguments parses and validates -> ValidationError
            raise web.HTTPUnprocessableEntity(
                text=json_dumps({"error": err.errors()}),
                content_type="application/json",
            ) from err

    return wrapped


# API ROUTES HANDLERS ---------------------------------------------------------
routes = web.RouteTableDef()


@routes.get(
    f"/{vtag}/projects/{{project_id}}/snapshots",
    name="_list_snapshots_handler",
)
@handle_request_errors
async def _list_snapshots_handler(request: web.Request):
    """
    Lists references on project snapshots
    """
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    snapshots = await list_snapshots(
        project_id=request.match_info["project_id"],  # type: ignore
    )

    # Append url links
    url_for_snapshot = request.app.router["_get_snapshot_handler"].url_for
    url_for_parameters = request.app.router["_get_snapshot_parameters_handler"].url_for

    for snp in snapshots:
        snp["url"] = url_for_snapshot(
            project_id=snp["parent_id"], snapshot_id=snp["id"]
        )
        snp["url_parameters"] = url_for_parameters(
            project_id=snp["parent_id"], snapshot_id=snp["id"]
        )
        # snp['url_project'] =

    return snapshots


@routes.get(
    f"/{vtag}/projects/{{project_id}}/snapshots/{{snapshot_id}}",
    name="_get_snapshot_handler",
)
@handle_request_errors
async def _get_snapshot_handler(request: web.Request):
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    snapshot = await get_snapshot(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_id=request.match_info["snapshot_id"],
    )
    return snapshot.json()


@routes.post(
    f"/{vtag}/projects/{{project_id}}/snapshots",
    name="_create_snapshot_handler",
)
@handle_request_errors
async def _create_snapshot_handler(request: web.Request):
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    snapshot = await create_snapshot(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_label=request.query.get("snapshot_label"),
    )

    return snapshot.json()


@routes.get(
    f"/{vtag}/projects/{{project_id}}/snapshots/{{snapshot_id}}/parameters",
    name="_get_snapshot_parameters_handler",
)
@handle_request_errors
async def _get_snapshot_parameters_handler(
    request: web.Request,
):
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    params = await get_snapshot_parameters(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_id=request.match_info["snapshot_id"],
    )

    return params


# API ROUTES HANDLERS ---------------------------------------------------------


@validate_arguments
async def list_snapshots(project_id: UUID) -> List[Dict[str, Any]]:
    # project_id is param-project?
    # TODO: add pagination
    # TODO: optimizaiton will grow snapshots of a project with time!
    #

    # snapshots:
    #   - ordered (iterations!)
    #   - have a parent project with all the parametrization
    #
    snapshot_info_0 = {
        "id": 0,
        "display_name": "snapshot 0",
        "parent_id": project_id,
        "parameters": get_snapshot_parameters(project_id, snapshot_id=str(id)),
    }

    return [
        snapshot_info_0,
    ]


@validate_arguments
async def get_snapshot(project_id: UUID, snapshot_id: str) -> Snapshot:
    # TODO: create a fake project
    # - generate project_id
    # - define what changes etc...
    pass


@validate_arguments
async def create_snapshot(
    project_id: UUID,
    snapshot_label: Optional[str] = None,
) -> Snapshot:
    pass


@validate_arguments
async def get_snapshot_parameters(project_id: UUID, snapshot_id: str):
    #
    return {"x": 4, "y": "yes"}
