from uuid import UUID

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

from ..._meta import API_VTAG
from ...application_settings_utils import requires_dev_feature_enabled
from ...login.decorators import login_required
from ...models import AuthenticatedRequestContext
from ...security.decorators import permission_required
from .. import notifications_service
from ._rest_exceptions import handle_notifications_exceptions

routes = web.RouteTableDef()
_notifications_prefix = f"/{API_VTAG}/notifications"


def _create_async_job_href(request: web.Request, route: str, task_uuid: UUID) -> str:
    task_id = f"{task_uuid}"
    path = f"{request.app.router[route].url_for(task_id=task_id)}"
    return f"{request.url.with_path(path)}"


@routes.post(f"{_notifications_prefix}/messages:send", name="send_message")
@login_required
@permission_required("notification.message.send")
@requires_dev_feature_enabled
@handle_notifications_exceptions
async def send_message(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    body = await parse_request_body_as(MessageBody, request)

    task_or_group_uuid, task_name = await notifications_service.send_message(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        channel=body.channel,
        group_ids=body.group_ids,
        # NOTE: external contacts are not supported for now from this endpoint, only group_ids
        external_contacts=None,
        content=body.content.model_dump(),
    )

    return create_data_response(
        TaskGet(
            task_id=f"{task_or_group_uuid}",
            task_name=task_name,
            status_href=_create_async_job_href(request, "get_async_job_status", task_or_group_uuid),
            abort_href=_create_async_job_href(request, "cancel_async_job", task_or_group_uuid),
            result_href=_create_async_job_href(request, "get_async_job_result", task_or_group_uuid),
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
        # NOTE: validated internally against the right template schema
        context=req_body.context,
    )

    return create_data_response(TemplatePreviewGet(**preview.model_dump()).data())


@routes.get(f"{_notifications_prefix}/templates:search", name="search_templates")
@login_required
@permission_required("notification.template.search")
@handle_notifications_exceptions
async def search_templates(request: web.Request) -> web.Response:
    query_params = parse_request_query_parameters_as(SearchTemplatesQueryParams, request)

    templates = await notifications_service.search_templates(
        request.app,
        channel=query_params.channel,
        template_name=query_params.template_name,
    )

    return create_data_response([TemplateGet(**template.model_dump()).data() for template in templates])
