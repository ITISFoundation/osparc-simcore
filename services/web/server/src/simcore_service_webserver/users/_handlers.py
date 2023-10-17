import functools
import logging

import redis.asyncio as aioredis
from aiohttp import web
from models_library.users import UserID
from pydantic import BaseModel, Field
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.logging_utils import get_log_record_extra, log_context
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.utils import fire_and_forget_task

from .._constants import RQ_PRODUCT_KEY
from .._meta import API_VTAG
from ..login._constants import MSG_LOGGED_OUT
from ..login.decorators import login_required
from ..login.utils import flash_response, notify_user_logout
from ..redis import get_redis_user_notifications_client
from ..security.api import check_password, forget
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _api, _tokens, api
from ._notifications import (
    MAX_NOTIFICATIONS_FOR_USER_TO_KEEP,
    MAX_NOTIFICATIONS_FOR_USER_TO_SHOW,
    UserNotification,
    UserNotificationCreate,
    UserNotificationPatch,
    get_notification_key,
)
from .exceptions import TokenNotFoundError, UserNotFoundError
from .schemas import (
    Permission,
    PermissionGet,
    ProfileCredentialsCheck,
    ProfileGet,
    ProfileUpdate,
    TokenCreate,
)

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[pydantic-alias]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[pydantic-alias]


def _handle_users_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except UserNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

    return wrapper


@routes.get(f"/{API_VTAG}/me", name="get_my_profile")
@login_required
@_handle_users_exceptions
async def get_my_profile(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    profile: ProfileGet = await api.get_user_profile(
        request.app, req_ctx.user_id, req_ctx.product_name
    )
    return envelope_json_response(profile)


@routes.put(f"/{API_VTAG}/me", name="update_my_profile")
@login_required
@permission_required("user.profile.update")
@_handle_users_exceptions
async def update_my_profile(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    profile_update = await parse_request_body_as(ProfileUpdate, request)
    await api.update_user_profile(request.app, req_ctx.user_id, profile_update)
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.post(f"/{API_VTAG}/me:mark-deleted", name="mark_account_for_deletion")
@login_required
@permission_required("user.profile.delete")
async def mark_account_for_deletion(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    body = await parse_request_body_as(ProfileCredentialsCheck, request)

    # checks before deleting
    credentials = await _api.get_user_credentials(request.app, user_id=req_ctx.user_id)
    if body.email != credentials.email.lower() or not check_password(
        body.password.get_secret_value(), credentials.password_hash
    ):
        raise web.HTTPConflict(
            reason="Wrong email or password. Please try again to delete this account"
        )

    with log_context(
        _logger,
        logging.INFO,
        "Mark account for deletion to %s",
        credentials.email,
        extra=get_log_record_extra(user_id=req_ctx.user_id),
    ):
        # update user table
        await _api.set_user_as_deleted(request.app, user_id=req_ctx.user_id)

        # logout
        await notify_user_logout(
            request.app, user_id=req_ctx.user_id, client_session_id=None
        )
        response = flash_response(MSG_LOGGED_OUT, "INFO")
        await forget(request, response)

        # send email in the background
        fire_and_forget_task(
            _api.send_close_account_email(
                request,
                user_email=credentials.email,
                user_name=credentials.full_name.first_name,
                retention_days=30,
            ),
            task_suffix_name=f"{__name__}.mark_account_for_deletion.send_close_account_email",
            fire_and_forget_tasks_collection=request.app[APP_FIRE_AND_FORGET_TASKS_KEY],
        )

        return response


# me/tokens/ ------------------------------------------------------
def _handle_tokens_errors(handler: Handler):
    @functools.wraps(handler)
    async def _wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except TokenNotFoundError as exc:
            raise web.HTTPNotFound(
                reason=f"Token for {exc.service_id} not found"
            ) from exc

    return _wrapper


@routes.get(f"/{API_VTAG}/me/tokens", name="list_tokens")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def list_tokens(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    all_tokens = await _tokens.list_tokens(request.app, req_ctx.user_id)
    return envelope_json_response(all_tokens)


@routes.post(f"/{API_VTAG}/me/tokens", name="create_token")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def create_token(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    token_create = await parse_request_body_as(TokenCreate, request)
    await _tokens.create_token(request.app, req_ctx.user_id, token_create)
    return envelope_json_response(token_create, web.HTTPCreated)


class _TokenPathParams(BaseModel):
    service: str


@routes.get(f"/{API_VTAG}/me/tokens/{{service}}", name="get_token")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def get_token(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    req_path_params = parse_request_path_parameters_as(_TokenPathParams, request)
    token = await _tokens.get_token(
        request.app, req_ctx.user_id, req_path_params.service
    )
    return envelope_json_response(token)


@routes.delete(f"/{API_VTAG}/me/tokens/{{service}}", name="delete_token")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def delete_token(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    req_path_params = parse_request_path_parameters_as(_TokenPathParams, request)
    await _tokens.delete_token(request.app, req_ctx.user_id, req_path_params.service)
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


# me/notifications -----------------------------------------------------------


async def _get_user_notifications(
    redis_client: aioredis.Redis, user_id: int
) -> list[UserNotification]:
    """returns a list of notifications where the latest notification is at index 0"""
    raw_notifications: list[str] = await redis_client.lrange(
        get_notification_key(user_id), -1 * MAX_NOTIFICATIONS_FOR_USER_TO_SHOW, -1
    )
    return [UserNotification.parse_raw(x) for x in raw_notifications]


@routes.get(f"/{API_VTAG}/me/notifications", name="list_user_notifications")
@login_required
@permission_required("user.notifications.read")
async def list_user_notifications(request: web.Request) -> web.Response:
    redis_client = get_redis_user_notifications_client(request.app)
    req_ctx = _RequestContext.parse_obj(request)
    notifications = await _get_user_notifications(redis_client, req_ctx.user_id)
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
        pipe.lpush(key, user_notification.json())
        pipe.ltrim(key, 0, MAX_NOTIFICATIONS_FOR_USER_TO_KEEP - 1)
        await pipe.execute()

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


class _NotificationPathParams(BaseModel):
    notification_id: str


@routes.patch(
    f"/{API_VTAG}/me/notifications/{{notification_id}}",
    name="mark_notification_as_read",
)
@login_required
@permission_required("user.notifications.update")
async def mark_notification_as_read(request: web.Request) -> web.Response:
    redis_client = get_redis_user_notifications_client(request.app)
    req_ctx = _RequestContext.parse_obj(request)
    req_path_params = parse_request_path_parameters_as(_NotificationPathParams, request)
    body = await parse_request_body_as(UserNotificationPatch, request)

    # NOTE: only the user's notifications can be patched
    key = get_notification_key(req_ctx.user_id)
    all_user_notifications: list[UserNotification] = [
        UserNotification.parse_raw(x) for x in await redis_client.lrange(key, 0, -1)
    ]
    for k, user_notification in enumerate(all_user_notifications):
        if req_path_params.notification_id == user_notification.id:
            user_notification.read = body.read
            await redis_client.lset(key, k, user_notification.json())
            raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.get(f"/{API_VTAG}/me/permissions", name="list_user_permissions")
@login_required
@permission_required("user.permissions.read")
async def list_user_permissions(request: web.Request) -> web.Response:
    req_ctx = _RequestContext.parse_obj(request)
    list_permissions: list[Permission] = await _api.list_user_permissions(
        request.app, req_ctx.user_id, req_ctx.product_name
    )
    return envelope_json_response(
        [
            PermissionGet.construct(_fields_set=p.__fields_set__, **p.dict())
            for p in list_permissions
        ]
    )
