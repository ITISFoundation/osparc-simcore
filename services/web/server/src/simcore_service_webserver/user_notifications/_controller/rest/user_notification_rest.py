import logging

import redis.asyncio as aioredis
from aiohttp import web
from common_library.json_serialization import json_loads
from models_library.api_schemas_webserver.users import MyPermissionGet
from models_library.users import UserPermission
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.redis import handle_redis_returns_union_types

from ...._meta import API_VTAG
from ....login.decorators import login_required
from ....products import products_web
from ....redis import get_redis_user_notifications_client
from ....security.decorators import permission_required
from ....users import _users_service
from ....users.schemas import UsersRequestContext
from ....utils_aiohttp import envelope_json_response
from ..._models import (
    MAX_NOTIFICATIONS_FOR_USER_TO_KEEP,
    MAX_NOTIFICATIONS_FOR_USER_TO_SHOW,
    UserNotification,
    UserNotificationCreate,
    UserNotificationPatch,
    get_notification_key,
)

_logger = logging.getLogger(__name__)


class NotificationPathParams(BaseModel):
    notification_id: str


routes = web.RouteTableDef()


async def _get_user_notifications(
    redis_client: aioredis.Redis, user_id: int, product_name: str
) -> list[UserNotification]:
    """returns a list of notifications where the latest notification is at index 0"""
    raw_notifications: list[str] = await handle_redis_returns_union_types(
        redis_client.lrange(
            get_notification_key(user_id), -1 * MAX_NOTIFICATIONS_FOR_USER_TO_SHOW, -1
        )
    )
    notifications = [json_loads(x) for x in raw_notifications]
    # Make it backwards compatible
    for n in notifications:
        if "product" not in n:
            n["product"] = "UNDEFINED"
    # Filter by product
    included = [product_name, "UNDEFINED"]
    filtered_notifications = [n for n in notifications if n["product"] in included]
    return [UserNotification.model_validate(x) for x in filtered_notifications]


@routes.get(f"/{API_VTAG}/me/notifications", name="list_user_notifications")
@login_required
@permission_required("user.notifications.read")
async def list_user_notifications(request: web.Request) -> web.Response:
    redis_client = get_redis_user_notifications_client(request.app)
    req_ctx = UsersRequestContext.model_validate(request)
    product_name = products_web.get_product_name(request)
    notifications = await _get_user_notifications(
        redis_client, req_ctx.user_id, product_name
    )
    return envelope_json_response(notifications)


@routes.post(f"/{API_VTAG}/me/notifications", name="create_user_notification")
@login_required
@permission_required("user.notifications.write")
async def create_user_notification(request: web.Request) -> web.Response:
    # body includes the updated notification
    body = await parse_request_body_as(UserNotificationCreate, request)
    user_notification = UserNotification.create_from_request_data(body)
    key = get_notification_key(user_notification.user_id)

    # insert at the head of the list and discard extra notifications
    redis_client = get_redis_user_notifications_client(request.app)
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.lpush(key, user_notification.model_dump_json())
        pipe.ltrim(key, 0, MAX_NOTIFICATIONS_FOR_USER_TO_KEEP - 1)
        await pipe.execute()

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


@routes.patch(
    f"/{API_VTAG}/me/notifications/{{notification_id}}",
    name="mark_notification_as_read",
)
@login_required
@permission_required("user.notifications.update")
async def mark_notification_as_read(request: web.Request) -> web.Response:
    redis_client = get_redis_user_notifications_client(request.app)
    req_ctx = UsersRequestContext.model_validate(request)
    req_path_params = parse_request_path_parameters_as(NotificationPathParams, request)
    body = await parse_request_body_as(UserNotificationPatch, request)

    # NOTE: only the user's notifications can be patched
    key = get_notification_key(req_ctx.user_id)
    all_user_notifications: list[UserNotification] = [
        UserNotification.model_validate_json(x)
        for x in await handle_redis_returns_union_types(redis_client.lrange(key, 0, -1))
    ]
    for k, user_notification in enumerate(all_user_notifications):
        if req_path_params.notification_id == user_notification.id:
            user_notification.read = body.read
            await handle_redis_returns_union_types(
                redis_client.lset(key, k, user_notification.model_dump_json())
            )
            return web.json_response(status=status.HTTP_204_NO_CONTENT)

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
