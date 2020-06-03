# pylint: disable=no-value-for-parameter

import json
import logging
from typing import Dict, List

import sqlalchemy as sa
import sqlalchemy.sql as sql
from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.result import RowProxy
from tenacity import retry

from servicelib.aiopg_utils import PostgresRetryPolicyUponOperation
from servicelib.application_keys import APP_DB_ENGINE_KEY

from . import users_api
from .db_models import GroupType, groups, tokens, user_to_groups, users
from .login.decorators import RQT_USERID_KEY, login_required
from .security_api import check_permission
from .security_decorators import permission_required
from .users_exceptions import (
    GroupNotFoundError,
    TokenNotFoundError,
    UserInGroupNotFoundError,
    UserNotFoundError,
)
from .utils import gravatar_hash

logger = logging.getLogger(__name__)


# me/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    # NOTE: ONLY login required to see its profile. E.g. anonymous can never see its profile
    uid = request[RQT_USERID_KEY]
    try:
        return await users_api.get_user_profile(request.app, uid)
    except UserNotFoundError:
        raise web.HTTPServerError(reason="could not find profile!")


@login_required
@permission_required("user.profile.update")
async def update_my_profile(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    # TODO: validate
    body = await request.json()

    async with engine.acquire() as conn:
        query = sa.select([users.c.name]).where(users.c.id == uid)
        default_name = await conn.scalar(query)
        parts = default_name.split(".") + [""]

    name = body.get("first_name", parts[0]) + "." + body.get("last_name", parts[1])

    async with engine.acquire() as conn:
        query = users.update().where(users.c.id == uid).values(name=name)
        resp = await conn.execute(query)
        assert resp.rowcount == 1  # nosec

    raise web.HTTPNoContent(content_type="application/json")


# me/groups/ ------------------------------------------------------
@login_required
@permission_required("user.groups.*")
async def list_groups(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    primary_group, user_groups, all_group = await users_api.list_user_groups(
        request.app, user_id
    )
    return {"me": primary_group, "organizations": user_groups, "all": all_group}


@login_required
@permission_required("user.groups.*")
async def get_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        return await users_api.get_user_group(request.app, user_id, gid)
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")


@login_required
@permission_required("user.groups.*")
async def create_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    new_group = await request.json()

    try:
        new_group = await users_api.create_user_group(request.app, user_id, new_group)
        raise web.HTTPCreated(
            text=json.dumps({"data": new_group}), content_type="application/json"
        )
    except UserNotFoundError:
        raise web.HTTPNotFound(reason=f"User not found")


@login_required
@permission_required("user.groups.*")
async def update_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    new_group_values = await request.json()

    try:
        return await users_api.update_user_group(
            request.app, user_id, gid, new_group_values
        )
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")


@login_required
@permission_required("user.groups.*")
async def delete_group(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        await users_api.delete_user_group(request.app, user_id, gid)
        raise web.HTTPNoContent()
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")


# me/groups/{gid}/users --------------------------------------------
@login_required
@permission_required("user.groups.*")
async def get_group_users(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    try:
        return await users_api.list_users_in_group(request.app, user_id, gid)
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")


@login_required
@permission_required("user.groups.*")
async def add_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    new_user_in_group = await request.json()
    assert "uid" in new_user_in_group
    try:
        await users_api.add_user_in_group(
            request.app, user_id, gid, new_user_in_group["uid"]
        )
        raise web.HTTPNoContent()
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")


@login_required
@permission_required("user.groups.*")
async def get_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    try:
        return await users_api.get_user_in_group(
            request.app, user_id, gid, the_user_id_in_group
        )
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInGroupNotFoundError:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found")


@login_required
@permission_required("user.groups.*")
async def update_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    new_values_for_user_in_group = await request.json()
    try:
        return await users_api.update_user_in_group(
            request.app,
            user_id,
            gid,
            the_user_id_in_group,
            new_values_for_user_in_group,
        )
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInGroupNotFoundError:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found")


@login_required
@permission_required("user.groups.*")
async def delete_group_user(request: web.Request):
    user_id = request[RQT_USERID_KEY]
    gid = request.match_info["gid"]
    the_user_id_in_group = request.match_info["uid"]
    try:
        await users_api.delete_user_in_group(
            request.app, user_id, gid, the_user_id_in_group
        )
        raise web.HTTPNoContent()
    except GroupNotFoundError:
        raise web.HTTPNotFound(reason=f"Group {gid} not found")
    except UserInGroupNotFoundError:
        raise web.HTTPNotFound(reason=f"User {the_user_id_in_group} not found")


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
    except TokenNotFoundError:
        raise web.HTTPNotFound(reason=f"Token for {service_id} not found")
