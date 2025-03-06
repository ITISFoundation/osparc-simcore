import logging

from aiohttp import web
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from .controller_rest_schemas import ServicePathParams, ServiceTagPathParams

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.get(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags",
    name="list_service_tags",
)
@login_required
@permission_required("service.tag.*")
async def list_service_tags(request: web.Request):
    path_params = parse_request_path_parameters_as(ServicePathParams, request)
    assert path_params  # nosec
    raise NotImplementedError


@routes.post(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}:add",
    name="add_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def add_service_tag(request: web.Request):
    path_params = parse_request_path_parameters_as(ServiceTagPathParams, request)
    assert path_params  # nosec

    # responds with parent's resource to get the current state (as with patch/update)
    raise NotImplementedError


@routes.post(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}:remove",
    name="remove_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def remove_service_tag(request: web.Request):
    path_params = parse_request_path_parameters_as(ServiceTagPathParams, request)
    assert path_params  # nosec

    # responds with parent's resource to get the current state (as with patch/update)
    raise NotImplementedError
