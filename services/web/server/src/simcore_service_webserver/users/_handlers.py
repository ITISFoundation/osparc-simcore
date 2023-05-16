import functools
from typing import Any

import redis.asyncio as aioredis
from aiohttp import web
from models_library.generics import Envelope
from pydantic import BaseModel
from servicelib.aiohttp.typing_extension import Handler
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..redis import get_redis_user_notifications_client
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _tokens, api
from ._notifications import (
    MAX_NOTIFICATIONS_FOR_USER_TO_KEEP,
    MAX_NOTIFICATIONS_FOR_USER_TO_SHOW,
    UserNotification,
    get_notification_key,
)
from .exceptions import TokenNotFoundError, UserNotFoundError
from .schemas import ProfileGet, ProfileUpdate


# me/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    # NOTE: ONLY login required to see its profile. E.g. anonymous can never see its profile
    uid = request[RQT_USERID_KEY]
    try:
        profile: ProfileGet = await api.get_user_profile(request.app, uid)
        return web.Response(
            text=Envelope[ProfileGet](data=profile).json(**RESPONSE_MODEL_POLICY),
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    except UserNotFoundError as exc:
        # NOTE: invalid user_id could happen due to timed-cache in AuthorizationPolicy
        raise web.HTTPNotFound(reason="Could not find profile!") from exc


@login_required
@permission_required("user.profile.update")
async def update_my_profile(request: web.Request):
    uid = request[RQT_USERID_KEY]
    body = await request.json()
    updates = ProfileUpdate.parse_obj(body)

    await api.update_user_profile(request.app, uid, updates)
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


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


@login_required
@permission_required("user.tokens.*")
async def create_tokens(request: web.Request):
    uid = request[RQT_USERID_KEY]
    body = await request.json()

    await _tokens.create_token(request.app, uid, body)
    raise web.HTTPCreated(
        text=json_dumps({"data": body}), content_type=MIMETYPE_APPLICATION_JSON
    )


@login_required
@permission_required("user.tokens.*")
async def list_tokens(request: web.Request):
    uid = request[RQT_USERID_KEY]
    all_tokens = await _tokens.list_tokens(request.app, uid)
    return envelope_json_response(all_tokens)


@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def get_token(request: web.Request):
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info["service"]

    one_token = await _tokens.get_token(request.app, uid, service_id)
    return envelope_json_response(one_token)


@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def update_token(request: web.Request):
    """updates token_data of a given user service

    WARNING: token_data has to be complete!
    """
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info["service"]
    token_data = await request.json()
    await _tokens.update_token(request.app, uid, service_id, token_data)
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def delete_token(request: web.Request):
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info["service"]

    await _tokens.delete_token(request.app, uid, service_id)
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


class UserNotificationsGet(BaseModel):
    data: list[UserNotification]


@login_required
async def get_user_notifications(request: web.Request):
    redis_client = get_redis_user_notifications_client(request.app)
    user_id = request[RQT_USERID_KEY]
    notifications = await _get_user_notifications(redis_client, user_id)
    return web.json_response(text=UserNotificationsGet(data=notifications).json())


@login_required
async def post_user_notification(request: web.Request):
    redis_client = get_redis_user_notifications_client(request.app)

    # body includes the updated notification
    notification_data: dict[str, Any] = await request.json()
    user_notification = UserNotification.create_from_request_data(notification_data)
    key = get_notification_key(user_notification.user_id)

    # insert at the head of the list and discard extra notifications
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.lpush(key, user_notification.json())
        pipe.ltrim(key, 0, MAX_NOTIFICATIONS_FOR_USER_TO_KEEP - 1)
        await pipe.execute()

    return web.json_response(status=web.HTTPNoContent.status_code)


routes = web.RouteTableDef()


@routes.patch(f"/{API_VTAG}/notifications/{{id}}", name="update_user_notification")
@login_required
async def update_user_notification(request: web.Request):
    redis_client = get_redis_user_notifications_client(request.app)
    user_id = request[RQT_USERID_KEY]
    notification_id = request.match_info["id"]

    # NOTE: only the user's notifications can be patched
    key = get_notification_key(user_id)
    all_user_notifications: list[UserNotification] = [
        UserNotification.parse_raw(x) for x in await redis_client.lrange(key, 0, -1)
    ]
    for k, user_notification in enumerate(all_user_notifications):
        if notification_id == user_notification.id:
            patch_data: dict[str, Any] = await request.json()
            user_notification.update_from(patch_data)
            await redis_client.lset(key, k, user_notification.json())
            return web.json_response(status=web.HTTPNoContent.status_code)

    return web.json_response(status=web.HTTPNotFound.status_code)
