from aiohttp import web
from models_library.api_schemas_notifications.template import NotificationsTemplateGet
from models_library.api_schemas_webserver.notifications import SearchTemplatesQueryParams
from pydantic import TypeAdapter
from servicelib.aiohttp.requests_validation import parse_request_query_parameters_as
from servicelib.aiohttp.rest_responses import create_data_response
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    search_templates as remote_search_templates,
)

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..rabbitmq import get_rabbitmq_rpc_client

routes = web.RouteTableDef()
_notifications_prefix = f"/{API_VTAG}/notifications"


@routes.get(f"{_notifications_prefix}/templates:search", name="search_templates")
@login_required
async def search_templates(request: web.Request) -> web.Response:
    query_params = parse_request_query_parameters_as(SearchTemplatesQueryParams, request)

    templates = await remote_search_templates(
        get_rabbitmq_rpc_client(request.app),
        channel=query_params.channel,
        template_name=query_params.template_name,
    )

    return create_data_response(TypeAdapter(list[NotificationsTemplateGet]).validate_python(templates))
