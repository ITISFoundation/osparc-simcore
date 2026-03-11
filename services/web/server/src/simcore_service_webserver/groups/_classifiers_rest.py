import logging

from aiohttp import web
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..scicrunch.models import ResourceHit
from ..scicrunch.scicrunch_service import SCICRUNCH_SERVICE_APPKEY
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ._classifiers_service import GroupClassifiersService
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.schemas import GroupsClassifiersQuery, GroupsPathParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/groups/{{gid}}/classifiers", name="get_group_classifiers")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def get_group_classifiers(request: web.Request):
    path_params = parse_request_path_parameters_as(GroupsPathParams, request)
    query_params: GroupsClassifiersQuery = parse_request_query_parameters_as(GroupsClassifiersQuery, request)

    service = GroupClassifiersService(request.app)
    view = await service.get_group_classifiers(path_params.gid, tree_view_mode=query_params.tree_view)

    return envelope_json_response(view)


@routes.get(
    f"/{API_VTAG}/groups/sparc/classifiers/scicrunch-resources/{{rrid}}",
    name="get_scicrunch_resource",
)
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def get_scicrunch_resource(request: web.Request):
    rrid = request.match_info["rrid"]

    service = request.app[SCICRUNCH_SERVICE_APPKEY]
    resource = await service.get_or_fetch_research_resource(rrid)

    return envelope_json_response(resource.model_dump())


@routes.post(
    f"/{API_VTAG}/groups/sparc/classifiers/scicrunch-resources/{{rrid}}",
    name="add_scicrunch_resource",
)
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def add_scicrunch_resource(request: web.Request):
    rrid = request.match_info["rrid"]

    service = request.app[SCICRUNCH_SERVICE_APPKEY]
    resource = await service.create_research_resource(rrid)

    return envelope_json_response(resource.model_dump())


@routes.get(
    f"/{API_VTAG}/groups/sparc/classifiers/scicrunch-resources:search",
    name="search_scicrunch_resources",
)
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def search_scicrunch_resources(request: web.Request):
    guess_name = str(request.query["guess_name"]).strip()

    service = request.app[SCICRUNCH_SERVICE_APPKEY]
    hits: list[ResourceHit] = await service.search_research_resources(guess_name)

    return envelope_json_response([hit.model_dump() for hit in hits])
