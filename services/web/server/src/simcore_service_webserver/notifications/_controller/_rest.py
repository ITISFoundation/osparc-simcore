import logging

from aiohttp import web
from celery_library.async_jobs import submit_job
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_notifications.message import EmailAddress, EmailContent, EmailNotificationMessage
from models_library.api_schemas_webserver.notifications import (
    NotificationsMessageBody,
    NotificationsTemplateGet,
    NotificationsTemplatePreviewBody,
    NotificationsTemplatePreviewGet,
    SearchTemplatesQueryParams,
)
from models_library.rpc.notifications.template import NotificationsTemplatePreviewRpcRequest
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import parse_request_body_as, parse_request_query_parameters_as
from servicelib.aiohttp.rest_responses import create_data_response
from servicelib.celery.models import ExecutionMetadata, OwnerMetadata
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    preview_template as remote_preview_template,
)
from servicelib.rabbitmq.rpc_interfaces.notifications.notifications_templates import (
    search_templates as remote_search_templates,
)

from ..._meta import API_VTAG
from ...celery import get_task_manager
from ...login.decorators import login_required
from ...models import AuthenticatedRequestContext, WebServerOwnerMetadata
from ...products._service import get_product
from ...rabbitmq import get_rabbitmq_rpc_client
from ...security.decorators import permission_required
from ...users._users_service import get_user, get_users_in_group
from .. import _service
from ._rest_exceptions import handle_notifications_exceptions

routes = web.RouteTableDef()
_notifications_prefix = f"/{API_VTAG}/notifications"


_logger = logging.getLogger(__name__)


@routes.post(f"{_notifications_prefix}/messages:send", name="send_message")
@login_required
@permission_required("admin.write")  # GCR: fix me
@handle_notifications_exceptions
async def send_message(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    body = await parse_request_body_as(NotificationsMessageBody, request)

    # GCR: move to service layer
    product = get_product(request.app, req_ctx.product_name)

    to: list[EmailAddress] = []

    for recipient in body.recipients:
        user_ids = await get_users_in_group(request.app, gid=recipient)
        for user_id in user_ids:
            user = await get_user(request.app, user_id=user_id)
            to.append(
                EmailAddress(
                    display_name=user["first_name"] or user["email"],
                    addr_spec=user["email"],
                )
            )

    message = EmailNotificationMessage(
        channel=body.channel,
        from_=EmailAddress(
            display_name=product.display_name,
            addr_spec=product.support_email,
        ),
        to=to,
        content=EmailContent(**body.content.model_dump()),
    )

    async_job_get = await submit_job(
        get_task_manager(request.app),
        execution_metadata=ExecutionMetadata(name=f"send_{body.channel}", queue="notifications"),
        owner_metadata=OwnerMetadata.model_validate(
            WebServerOwnerMetadata(
                user_id=req_ctx.user_id,
                product_name=req_ctx.product_name,
            ).model_dump()
        ),
        message=message.model_dump(),
    )

    task_id = f"{async_job_get.job_id}"

    return create_data_response(
        TaskGet(
            task_id=task_id,
            task_name=async_job_get.job_name,
            status_href=f"{request.url.with_path(str(request.app.router['get_async_job_status'].url_for(task_id=task_id)))}",
            abort_href=f"{request.url.with_path(str(request.app.router['cancel_async_job'].url_for(task_id=task_id)))}",
            result_href=f"{request.url.with_path(str(request.app.router['get_async_job_result'].url_for(task_id=task_id)))}",
        ),
        status=status.HTTP_202_ACCEPTED,
    )


@routes.post(f"{_notifications_prefix}/templates:preview", name="preview_template")
@login_required
@permission_required("admin.read")  # GCR: fix me
@handle_notifications_exceptions
async def preview_template(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    body = await parse_request_body_as(NotificationsTemplatePreviewBody, request)

    product_data = _service.create_product_data(app=request.app, product_name=req_ctx.product_name)

    enriched_body = body.model_copy(update={"context": {**body.context, "product": product_data}}, deep=True)

    preview = await remote_preview_template(
        get_rabbitmq_rpc_client(request.app),
        request=NotificationsTemplatePreviewRpcRequest(**enriched_body.model_dump()),
    )

    return create_data_response(NotificationsTemplatePreviewGet(**preview.model_dump()).data())


@routes.get(f"{_notifications_prefix}/templates:search", name="search_templates")
@login_required
@permission_required("admin.read")  # GCR: fix me
@handle_notifications_exceptions
async def search_templates(request: web.Request) -> web.Response:
    query_params = parse_request_query_parameters_as(SearchTemplatesQueryParams, request)

    templates = await remote_search_templates(
        get_rabbitmq_rpc_client(request.app),
        channel=query_params.channel,
        template_name=query_params.template_name,
    )

    return create_data_response([NotificationsTemplateGet(**template.model_dump()).data() for template in templates])
