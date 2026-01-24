import logging

from aiohttp import web
from models_library.api_schemas_webserver.notifications import (
    NotificationsTemplateGet,
    NotificationsTemplatePreviewBody,
    NotificationsTemplatePreviewGet,
    SearchTemplatesQueryParams,
)
from models_library.rpc.notifications.template import NotificationsTemplatePreviewRpcRequest
from servicelib.aiohttp.requests_validation import parse_request_body_as, parse_request_query_parameters_as
from servicelib.aiohttp.rest_responses import create_data_response
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    preview_template as remote_preview_template,
)
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    search_templates as remote_search_templates,
)

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..rabbitmq import get_rabbitmq_rpc_client
from ._rest_exceptions import handle_notifications_exceptions

routes = web.RouteTableDef()
_notifications_prefix = f"/{API_VTAG}/notifications"


# TODO: POST /notifications/templates:send  # noqa: FIX002
# TODO: POST /notifications/messages:send  # noqa: FIX002

_logger = logging.getLogger(__name__)


@routes.post(f"{_notifications_prefix}/templates:preview", name="preview_template")
@login_required
@handle_notifications_exceptions
async def preview_template(request: web.Request) -> web.Response:
    body = await parse_request_body_as(NotificationsTemplatePreviewBody, request)

    _logger.error({"body": body})

    preview = await remote_preview_template(
        get_rabbitmq_rpc_client(request.app),
        request=NotificationsTemplatePreviewRpcRequest(**body.model_dump()),
    )

    return create_data_response(NotificationsTemplatePreviewGet(**preview.model_dump()).data())


@routes.get(f"{_notifications_prefix}/templates:search", name="search_templates")
@login_required
@handle_notifications_exceptions
async def search_templates(request: web.Request) -> web.Response:
    query_params = parse_request_query_parameters_as(SearchTemplatesQueryParams, request)

    templates = await remote_search_templates(
        get_rabbitmq_rpc_client(request.app),
        channel=query_params.channel,
        template_name=query_params.template_name,
    )

    return create_data_response([NotificationsTemplateGet(**template.model_dump()).data() for template in templates])
