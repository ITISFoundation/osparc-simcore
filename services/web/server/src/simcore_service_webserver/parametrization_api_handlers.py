import json
from functools import wraps
from typing import Any, Callable, Dict, List
from uuid import UUID

from aiohttp import web
from aiohttp.web_routedef import RouteDef
from models_library.projects import Project
from pydantic.decorator import validate_arguments
from pydantic.error_wrappers import ValidationError

from ._meta import api_version_prefix
from .constants import RQ_PRODUCT_KEY, RQT_USERID_KEY

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


@routes.get(f"/{api_version_prefix}/projects/{{project_id}}/snapshots")
@handle_request_errors
async def _list_project_snapshots_handler(request: web.Request):
    """
    Lists references on project snapshots
    """
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    snapshots = await list_project_snapshots(
        project_id=request.match_info["project_id"],  # type: ignore
    )

    # Append url links
    url_for_snapshot = request.app.router["_get_project_snapshot_handler"].url_for
    url_for_parameters = request.app.router[
        "_get_project_snapshot_parameters_handler"
    ].url_for

    for snp in snapshots:
        snp["url"] = url_for_snapshot(
            project_id=snp["parent_id"], snapshot_id=snp["id"]
        )
        snp["url_parameters"] = url_for_parameters(
            project_id=snp["parent_id"], snapshot_id=snp["id"]
        )
        # snp['url_project'] =

    return snapshots


@validate_arguments
async def list_project_snapshots(project_id: UUID) -> List[Dict[str, Any]]:
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
        "parameters": get_project_snapshot_parameters(project_id, snapshot_id=str(id)),
    }

    return [
        snapshot_info_0,
    ]


@routes.get(f"/{api_version_prefix}/projects/{{project_id}}/snapshots/{{snapshot_id}}")
@handle_request_errors
async def _get_project_snapshot_handler(request: web.Request):
    """
    Returns full project. Equivalent to /projects/{snapshot_project_id}
    """
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    prj_dict = await get_project_snapshot(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_id=request.match_info["snapshot_id"],
    )
    return prj_dict  # ???


@validate_arguments
async def get_project_snapshot(project_id: UUID, snapshot_id: str) -> Dict[str, Any]:
    # TODO: create a fake project
    # - generate project_id
    # - define what changes etc...
    project = Project()
    return project.dict()


@routes.get(
    f"/{api_version_prefix}/projects/{{project_id}}/snapshots/{{snapshot_id}}/parameters"
)
@handle_request_errors
async def _get_project_snapshot_parameters_handler(
    request: web.Request,
):
    # GET /projects/{id}/snapshots/{id}/parametrization  -> {x:3, y:0, ...}
    user_id, product_name = request[RQT_USERID_KEY], request[RQ_PRODUCT_KEY]

    params = await get_project_snapshot_parameters(
        project_id=request.match_info["project_id"],  # type: ignore
        snapshot_id=request.match_info["snapshot_id"],
    )

    return params


@validate_arguments
async def get_project_snapshot_parameters(
    project_id: UUID, snapshot_id: str
) -> Dict[str, Any]:
    #
    return {"x": 4, "y": "yes"}


# -------------------------------------
assert routes  # nosec

# NOTE: names all routes with handler's
# TODO: override routes functions ?
for route_def in routes:
    assert isinstance(route_def, RouteDef)  # nosec
    route_def.kwargs["name"] = route_def.handler.__name__
