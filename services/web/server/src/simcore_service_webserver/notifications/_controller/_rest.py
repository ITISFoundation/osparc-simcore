from aiohttp import web
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_webserver.notifications import (
    MessageBody,
    SearchTemplatesQueryParams,
    TemplateGet,
    TemplatePreviewBody,
    TemplatePreviewGet,
)
from models_library.notifications import TemplateRef
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_body_as, parse_request_query_parameters_as
from servicelib.aiohttp.rest_responses import create_data_response
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    search_templates as remote_search_templates,
)

from ..._meta import API_VTAG
from ...login.decorators import login_required
from ...models import AuthenticatedRequestContext
from ...rabbitmq import get_rabbitmq_rpc_client
from ...security.decorators import permission_required
from .. import notifications_service
from ._rest_exceptions import handle_notifications_exceptions

routes = web.RouteTableDef()
_notifications_prefix = f"/{API_VTAG}/notifications"


@routes.post(f"{_notifications_prefix}/messages:send", name="send_message")
@login_required
@permission_required("notification.message.send")
@handle_notifications_exceptions
async def send_message(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    body = await parse_request_body_as(MessageBody, request)

    async_job = await notifications_service.send_message(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        channel=body.channel,
        group_ids=body.group_ids,
        # NOTE: external contacts are not supported for now from this endpoint, only group_ids
        external_contacts=None,
        message_content=body.message_content.model_dump(),
    )

    task_id = f"{async_job.job_id}"

    return create_data_response(
        TaskGet(
            task_id=task_id,
            task_name=async_job.job_name,
            status_href=f"{request.url.with_path(str(request.app.router['get_async_job_status'].url_for(task_id=task_id)))}",
            abort_href=f"{request.url.with_path(str(request.app.router['cancel_async_job'].url_for(task_id=task_id)))}",
            result_href=f"{request.url.with_path(str(request.app.router['get_async_job_result'].url_for(task_id=task_id)))}",
        ),
        status=status.HTTP_202_ACCEPTED,
    )


@routes.post(f"{_notifications_prefix}/templates:preview", name="preview_template")
@login_required
@permission_required("notification.template.preview")
@handle_notifications_exceptions
async def preview_template(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    req_body = await parse_request_body_as(TemplatePreviewBody, request)

    preview = await notifications_service.preview_template(
        request.app,
        product_name=req_ctx.product_name,
        ref=TemplateRef(**req_body.ref.model_dump()),
        context=req_body.context,
    )

    return create_data_response(TemplatePreviewGet(**preview.model_dump()).data())


@routes.get(f"{_notifications_prefix}/templates:search", name="search_templates")
@login_required
@permission_required("notification.template.search")
@handle_notifications_exceptions
async def search_templates(request: web.Request) -> web.Response:
    query_params = parse_request_query_parameters_as(SearchTemplatesQueryParams, request)

    templates = await remote_search_templates(
        get_rabbitmq_rpc_client(request.app),
        channel=query_params.channel,
        template_name=query_params.template_name,
    )

    return create_data_response([TemplateGet(**template.model_dump()).data() for template in templates])
