import logging

from aiohttp import web

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


@routes.put(
    f"{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}",
    name="add_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def add_service_tag(request: web.Request):
    raise NotImplementedError


@routes.delete(
    f"/{API_VTAG}/catalog/services/{{service_key}}/{{service_version}}/tags/{{tag_id}}",
    name="remove_service_tag",
)
@login_required
@permission_required("service.tag.*")
async def remove_service_tag(request: web.Request):
    raise NotImplementedError
