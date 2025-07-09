import logging

from aiohttp import web
from models_library.api_schemas_webserver.users import MyPermissionGet
from models_library.users import UserPermission
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)

from ...._meta import API_VTAG
from ....login.decorators import login_required
from ....products import products_web
from ....security.decorators import permission_required
from ....users import _users_service
from ....users.schemas import UsersRequestContext
from ....utils_aiohttp import envelope_json_response
from ... import _service
from ..._models import UserNotificationCreate, UserNotificationPatch

_logger = logging.getLogger(__name__)


class NotificationPathParams(BaseModel):
    notification_id: str


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/me/notifications", name="list_user_notifications")
@login_required
@permission_required("user.notifications.read")
async def list_user_notifications(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    product_name = products_web.get_product_name(request)
    notifications = await _service.list_user_notifications(
        request.app, req_ctx.user_id, product_name
    )
    return envelope_json_response(notifications)


@routes.post(f"/{API_VTAG}/me/notifications", name="create_user_notification")
@login_required
@permission_required("user.notifications.write")
async def create_user_notification(request: web.Request) -> web.Response:
    body = await parse_request_body_as(UserNotificationCreate, request)
    await _service.create_user_notification(request.app, body)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.patch(
    f"/{API_VTAG}/me/notifications/{{notification_id}}",
    name="mark_notification_as_read",
)
@login_required
@permission_required("user.notifications.update")
async def mark_notification_as_read(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    req_path_params = parse_request_path_parameters_as(NotificationPathParams, request)
    body = await parse_request_body_as(UserNotificationPatch, request)

    await _service.update_user_notification(
        request.app,
        req_ctx.user_id,
        req_path_params.notification_id,
        body.model_dump(exclude_unset=True),
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.get(f"/{API_VTAG}/me/permissions", name="list_user_permissions")
@login_required
@permission_required("user.permissions.read")
async def list_user_permissions(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    list_permissions: list[UserPermission] = await _users_service.list_user_permissions(
        request.app, user_id=req_ctx.user_id, product_name=req_ctx.product_name
    )
    return envelope_json_response(
        [MyPermissionGet.from_domain_model(p) for p in list_permissions]
    )
