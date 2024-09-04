import logging

from aiohttp import web
from models_library.api_schemas_webserver.catalog import CatalogServiceGet
from models_library.basic_types import IdInt
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..tags.schemas import TagGet
from ._handlers import ServicePathParams

_logger = logging.getLogger(__name__)


class ServiceTagPathParams(ServicePathParams):
    tag_id: IdInt


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

    assert list[TagGet]  # nosec
    raise NotImplementedError


@routes.put(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}",
    name="add_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def add_service_tag(request: web.Request):
    path_params = parse_request_path_parameters_as(ServiceTagPathParams, request)
    assert path_params  # nosec

    # responds with parent's resource to get the current state (as with patch/update)
    assert CatalogServiceGet  # nosec
    raise NotImplementedError


@routes.delete(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}",
    name="remove_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def remove_service_tag(request: web.Request):
    path_params = parse_request_path_parameters_as(ServiceTagPathParams, request)
    assert path_params  # nosec

    # responds with parent's resource to get the current state (as with patch/update)
    assert CatalogServiceGet  # nosec
    raise NotImplementedError
