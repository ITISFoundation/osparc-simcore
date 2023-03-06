# pylint: disable=no-value-for-parameter

import json
import logging
import random

from aiohttp import web
from models_library.generics import Envelope
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from . import users_api
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


@login_required
async def get_user_notifications(request: web.Request):
    redis_client = get_redis_user_notifications_client(request.app)
    user_id = request[RQT_USERID_KEY]
    notifications = []
    user_hash_key = f'user_id={user_id}:notification_id=*'
    async for scanned_notification_key in redis_client.scan_iter(match=user_hash_key):
        if notification_str := await redis_client.get(scanned_notification_key):
            print("notification_str", notification_str)
            notifications.append(notification_str)
    return web.json_response(data={"data": notifications})


@login_required
async def post_user_notification(request: web.Request):
    print("post_user_notification", request)
    redis_client = get_redis_user_notifications_client(request.app)
    user_id = 1
    nid = random.randint(100, 1000)
    user_hash_key = f'user_id={user_id}:notification_id={nid}'
    notification = {
        "user_id": user_id,
        "read": "False"
    }
    await redis_client.set(user_hash_key, value=notification)
    response = web.json_response(status=web.HTTPNoContent.status_code)
    assert response.status == 204  # nosec
    return response


@login_required
async def update_user_notification(request: web.Request):
    print(request)
    response = web.json_response(status=web.HTTPNoContent.status_code)
    assert response.status == 204  # nosec
    return response
