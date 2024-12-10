import logging

from aiohttp import web
from servicelib.aiohttp.requests_validation import (
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..scicrunch.db import ResearchResourceRepository
from ..scicrunch.errors import ScicrunchError
from ..scicrunch.models import ResearchResource, ResourceHit
from ..scicrunch.service_client import SciCrunch
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from ._classifiers_api import GroupClassifierRepository, build_rrids_tree_view
from ._common.exceptions_handlers import handle_plugin_requests_exceptions
from ._common.schemas import GroupsClassifiersQuery, GroupsPathParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/groups/{{gid}}/classifiers", name="get_group_classifiers")
@login_required
@permission_required("groups.*")
@handle_plugin_requests_exceptions
async def get_group_classifiers(request: web.Request):
    try:
        path_params = parse_request_path_parameters_as(GroupsPathParams, request)
        query_params: GroupsClassifiersQuery = parse_request_query_parameters_as(
            GroupsClassifiersQuery, request
        )

        repo = GroupClassifierRepository(request.app)
        if not await repo.group_uses_scicrunch(path_params.gid):
            bundle = await repo.get_classifiers_from_bundle(path_params.gid)
            return envelope_json_response(bundle)

        # otherwise, build dynamic tree with RRIDs
        view = await build_rrids_tree_view(
            request.app, tree_view_mode=query_params.tree_view
        )
    except ScicrunchError:
        view = {}

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
    rrid = SciCrunch.validate_identifier(rrid)

    # check if in database first
    repo = ResearchResourceRepository(request.app)
    resource: ResearchResource | None = await repo.get_resource(rrid)
    if not resource:
        # otherwise, request to scicrunch service
        scicrunch = SciCrunch.get_instance(request.app)
        resource = await scicrunch.get_resource_fields(rrid)

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

    # check if exists
    repo = ResearchResourceRepository(request.app)
    resource: ResearchResource | None = await repo.get_resource(rrid)
    if not resource:
        # then request scicrunch service
        scicrunch = SciCrunch.get_instance(request.app)
        resource = await scicrunch.get_resource_fields(rrid)

        # insert new or if exists, then update
        await repo.upsert(resource)

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

    scicrunch = SciCrunch.get_instance(request.app)
    hits: list[ResourceHit] = await scicrunch.search_resource(guess_name)

    return envelope_json_response([hit.model_dump() for hit in hits])
