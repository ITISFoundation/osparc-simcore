# pylint: disable=no-value-for-parameter

import json
import logging

from aiohttp import web

from . import users_api
from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required
from .users_exceptions import TokenNotFoundError, UserNotFoundError

logger = logging.getLogger(__name__)


# me/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    # NOTE: ONLY login required to see its profile. E.g. anonymous can never see its profile
    uid = request[RQT_USERID_KEY]
    try:
        return await users_api.get_user_profile(request.app, uid)
    except UserNotFoundError as exc:
        # NOTE: invalid user_id could happen due to timed-cache in AuthorizationPolicy
        raise web.HTTPNotFound(reason="Could not find profile!") from exc


@login_required
@permission_required("user.profile.update")
async def update_my_profile(request: web.Request):
    uid = request[RQT_USERID_KEY]

    # TODO: validate
    body = await request.json()

    await users_api.update_user_profile(request.app, uid, body)
    raise web.HTTPNoContent(content_type="application/json")


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
        text=json.dumps({"data": body}), content_type="application/json"
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
    """ updates token_data of a given user service

    WARNING: token_data has to be complete!
    """
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info["service"]

    # TODO: validate
    body = await request.json()

    await users_api.update_token(request.app, uid, service_id, body)

    raise web.HTTPNoContent(content_type="application/json")


@login_required
@permission_required("user.tokens.*")
async def delete_token(request: web.Request):
    uid = request[RQT_USERID_KEY]
    service_id = request.match_info.get("service")

    try:
        await users_api.delete_token(request.app, uid, service_id)
        raise web.HTTPNoContent(content_type="application/json")
    except TokenNotFoundError as exc:
        raise web.HTTPNotFound(reason=f"Token for {service_id} not found") from exc
