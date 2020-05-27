# pylint: disable=no-value-for-parameter

import json
import logging
from typing import List

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
from .utils import gravatar_hash

logger = logging.getLogger(__name__)


# me/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    # NOTE: ONLY login required to see its profile. E.g. anonymous can never see its profile

    @retry(**PostgresRetryPolicyUponOperation(logger).kwargs)
    async def _query_db(uid: str, engine: Engine) -> List[RowProxy]:
        async with engine.acquire() as conn:
            query = (
                sa.select(
                    [
                        users.c.email,
                        users.c.role,
                        users.c.name,
                        users.c.primary_gid,
                        groups.c.gid,
                        groups.c.name,
                        groups.c.description,
                        groups.c.type,
                    ],
                    use_labels=True,
                )
                .select_from(
                    users.join(
                        user_to_groups.join(
                            groups, user_to_groups.c.gid == groups.c.gid
                        ),
                        users.c.id == user_to_groups.c.uid,
                    )
                )
                .where(users.c.id == uid)
                .order_by(sa.asc(groups.c.name))
            )
            result = await conn.execute(query)
            return await result.fetchall()

    # here we get all user_group combinations but only the group changes
    user_groups: List[RowProxy] = await _query_db(
        uid=request[RQT_USERID_KEY], engine=request.app[APP_DB_ENGINE_KEY]
    )

    if not user_groups:
        raise web.HTTPServerError(reason="could not find profile!")

    # get the primary group and the all group
    user_primary_group = all_group = {}
    other_groups = []
    for user_group in user_groups:
        if user_group["users_primary_gid"] == user_group["groups_gid"]:
            user_primary_group = user_group
        elif user_group["groups_type"] == GroupType.EVERYONE:
            all_group = user_group
        else:
            other_groups.append(user_group)

    parts = user_primary_group["users_name"].split(".") + [""]
    return {
        "login": user_primary_group["users_email"],
        "first_name": parts[0],
        "last_name": parts[1],
        "role": user_primary_group["users_role"].name.capitalize(),
        "gravatar_id": gravatar_hash(user_primary_group["users_email"]),
        "groups": {
            "me": {
                "gid": user_primary_group["groups_gid"],
                "label": user_primary_group["groups_name"],
                "description": user_primary_group["groups_description"],
            },
            "organizations": [
                {
                    "gid": group["groups_gid"],
                    "label": group["groups_name"],
                    "description": group["groups_description"],
                }
                for group in other_groups
            ],
            "all": {
                "gid": all_group["groups_gid"],
                "label": all_group["groups_name"],
                "description": all_group["groups_description"],
            },
        },
    }


@login_required
async def update_my_profile(request: web.Request):
    await check_permission(request, "user.profile.update")

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


@login_required
@permission_required("user.groups.read")
async def list_groups(request: web.Request):
    uid = request[RQT_USERID_KEY]
    primary_group, user_groups, all_group = await users_api.list_user_groups(
        request.app, uid
    )
    return {"me": primary_group, "organizations": user_groups, "all": all_group}


@login_required
@permission_required(permissions="user.groups.read")
async def get_group(request: web.Request):
    pass


@login_required
@permission_required(permissions="user.groups.list")
async def get_group_users(request: web.Request):
    pass


@login_required
@permission_required(permissions="user.groups.create")
async def create_group(request: web.Request):
    pass


@login_required
@permission_required(permissions="user.groups.update")
async def update_group(request: web.Request):
    pass


@login_required
@permission_required(permissions="user.groups.delete")
async def delete_group(request: web.Request):
    pass


# me/tokens/ ------------------------------------------------------
@login_required
async def create_tokens(request: web.Request):
    await check_permission(request, "user.tokens.*")

    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    # TODO: validate
    body = await request.json()

    # TODO: what it service exists already!?
    # TODO: if service already, then IntegrityError is raised! How to deal with db exceptions??
    async with engine.acquire() as conn:
        stmt = tokens.insert().values(
            user_id=uid, token_service=body["service"], token_data=body
        )
        await conn.execute(stmt)

        raise web.HTTPCreated(
            text=json.dumps({"data": body}), content_type="application/json"
        )


@login_required
async def list_tokens(request: web.Request):
    await check_permission(request, "user.tokens.*")

    # TODO: start = request.match_info.get('start', 0)
    # TODO: count = request.match_info.get('count', None)
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    user_tokens = []
    async with engine.acquire() as conn:
        query = sa.select([tokens.c.token_data]).where(tokens.c.user_id == uid)
        async for row in conn.execute(query):
            user_tokens.append(row["token_data"])

    return user_tokens


@login_required
async def get_token(request: web.Request):
    await check_permission(request, "user.tokens.*")

    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    service_id = request.match_info["service"]

    async with engine.acquire() as conn:
        query = sa.select([tokens.c.token_data]).where(
            sql.and_(tokens.c.user_id == uid, tokens.c.token_service == service_id)
        )
        result = await conn.execute(query)
        row = await result.first()
        return row["token_data"]


@login_required
async def update_token(request: web.Request):
    """ updates token_data of a given user service

    WARNING: token_data has to be complete!
    """
    await check_permission(request, "user.tokens.*")

    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    service_id = request.match_info["service"]

    # TODO: validate
    body = await request.json()

    # TODO: optimize to a single call?
    async with engine.acquire() as conn:
        query = sa.select([tokens.c.token_data, tokens.c.token_id]).where(
            sql.and_(tokens.c.user_id == uid, tokens.c.token_service == service_id)
        )
        result = await conn.execute(query)
        row = await result.first()

        data = dict(row["token_data"])
        tid = row["token_id"]
        data.update(body)

        query = tokens.update().where(tokens.c.token_id == tid).values(token_data=data)
        resp = await conn.execute(query)
        assert resp.rowcount == 1  # nosec

    raise web.HTTPNoContent(content_type="application/json")


@login_required
async def delete_token(request: web.Request):
    await check_permission(request, "user.tokens.*")

    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    service_id = request.match_info.get("service")

    async with engine.acquire() as conn:
        query = tokens.delete().where(
            sql.and_(tokens.c.user_id == uid, tokens.c.token_service == service_id)
        )
        await conn.execute(query)

    raise web.HTTPNoContent(content_type="application/json")
