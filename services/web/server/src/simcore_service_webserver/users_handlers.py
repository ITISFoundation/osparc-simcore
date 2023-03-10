# pylint: disable=no-value-for-parameter

import json
import logging
from uuid import uuid4

from aiohttp import web
from models_library.generics import Envelope
import redis.asyncio as aioredis
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from . import users_api
from ._meta import API_VTAG
from .login.decorators import RQT_USERID_KEY, login_required
from .redis import get_redis_user_notifications_client
from .security_decorators import permission_required
from .users_exceptions import TokenNotFoundError, UserNotFoundError
from .users_models import ProfileGet, ProfileUpdate

logger = logging.getLogger(__name__)


# me/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    # NOTE: ONLY login required to see its profile. E.g. anonymous can never see its profile
    uid = request[RQT_USERID_KEY]
    try:
        profile: ProfileGet = await users_api.get_user_profile(request.app, uid)
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

    await users_api.update_user_profile(request.app, uid, updates)
    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


# me/tokens/ ------------------------------------------------------
@login_required
@permission_required("user.tokens.*")
async def create_tokens(request: web.Request):
    uid = request[RQT_USERID_KEY]

    # TODO: validate
    body = await request.json()

    # TODO: what it service exists already!?
    # TODO: if service already, then IntegrityError is raised! How to deal with db exceptions??
    await users_api.create_token(request.app, uid, body)
    raise web.HTTPCreated(
        text=json.dumps({"data": body}), content_type=MIMETYPE_APPLICATION_JSON
    )


@login_required
@permission_required("user.tokens.*")
async def list_tokens(request: web.Request):
    # TODO: start = request.match_info.get('start', 0)
    # TODO: count = request.match_info.get('count', None)
    uid = request[RQT_USERID_KEY]
    return await users_api.list_tokens(request.app, uid)


@login_required
@permission_required("user.tokens.*")
async def get_token(request: web.Request):
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info["service"]

    return await users_api.get_token(request.app, uid, service_id)


@login_required
@permission_required("user.tokens.*")
async def update_token(request: web.Request):
    """updates token_data of a given user service

    WARNING: token_data has to be complete!
    """
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info["service"]

    # TODO: validate
    body = await request.json()

    await users_api.update_token(request.app, uid, service_id, body)

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@login_required
@permission_required("user.tokens.*")
async def delete_token(request: web.Request):
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info.get("service")

    try:
        await users_api.delete_token(request.app, uid, service_id)
        raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
    except TokenNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Token for {service_id} not found") from exc


# me/notifications -----------------------------------------------------------

async def _get_user_notifications(redis_client: aioredis.Redis, user_id: int):
    notifs = []
    user_hash_key = f'user_id={user_id}'
    llen = await redis_client.llen(user_hash_key)
    if notifs_list := await redis_client.lrange(user_hash_key, 0, llen):
        print("notifs_list", notifs_list)
        for notif_str in notifs_list:
            notif = json.loads(notif_str)
            notifs.append(notif)
    return notifs


@login_required
async def get_user_notifications(request: web.Request):
    redis_client = get_redis_user_notifications_client(request.app)
    user_id = request[RQT_USERID_KEY]
    notifs = await _get_user_notifications(redis_client, user_id)
    # last 10 items only
    return web.json_response(data={"data": notifs[-10:]})


@login_required
async def post_user_notification(request: web.Request):
    redis_client = get_redis_user_notifications_client(request.app)
    # body includes the new notification
    notif = await request.json()
    nid = str(uuid4())
    notif["id"] = nid
    notif["read"] = False
    user_hash_key = f'user_id={notif["user_id"]}'
    # insert at the head of the list
    await redis_client.lpushx(user_hash_key, json.dumps(notif))
    return web.json_response(status=web.HTTPNoContent.status_code)


routes = web.RouteTableDef()


@routes.patch(f"/{API_VTAG}/notifications/{{nid}}", name="update_user_notification")
@login_required
async def update_user_notification(request: web.Request):
    redis_client = get_redis_user_notifications_client(request.app)
    user_id = request[RQT_USERID_KEY]
    nid = request.match_info["nid"]
    notifs = await _get_user_notifications(redis_client, user_id)
    notif_idx = next((idx for (idx, n) in enumerate(notifs) if n["id"] == nid), None)
    if notif_idx:
        notif = notifs[notif_idx]
        # body includes a dict with the changes to make
        body = await request.json()
        for k, v in body.items():
            notif[k] = v
        user_hash_key = f'user_id={notif["user_id"]}'
        await redis_client.lset(user_hash_key, notif_idx, json.dumps(notif))
        return web.json_response(status=web.HTTPNoContent.status_code)
    return web.json_response(status=web.HTTPNotFound.status_code)
