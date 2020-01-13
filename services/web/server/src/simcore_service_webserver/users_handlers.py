# pylint: disable=no-value-for-parameter

import json
import logging

import sqlalchemy as sa
import sqlalchemy.sql as sql
from aiohttp import web
from servicelib.aiopg_utils import PostgresRetryPolicyUponOperation
from servicelib.application_keys import APP_DB_ENGINE_KEY
from tenacity import retry

from .db_models import tokens, users
from .login.decorators import RQT_USERID_KEY, login_required
from .security_api import check_permission
from .utils import gravatar_hash

logger = logging.getLogger(__name__)


# me/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    # NOTE: ONLY login required to see its profile. E.g. anonymous can never see its profile

    @retry(**PostgresRetryPolicyUponOperation(logger).kwargs)
    def _query_user_to_db(uid, engine):
        async with engine.acquire() as conn:
            query = sa.select([
                users.c.email,
                users.c.role,
                users.c.name]).where(users.c.id == uid)
            result = await conn.execute(query)
            return await result.first()

    row = _query_user_to_db(uid=request[RQT_USERID_KEY], engine=request.app[APP_DB_ENGINE_KEY])
    parts = row['name'].split(".") + [""]

    return {
        'login': row['email'],
        'first_name': parts[0],
        'last_name': parts[1],
        'role': row['role'].name.capitalize(),
        'gravatar_id': gravatar_hash(row['email'])
    }


@login_required
async def update_my_profile(request: web.Request):
    await check_permission(request, "user.profile.update")

    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    # TODO: validate
    body = await request.json()

    async with engine.acquire() as conn:
        query = sa.select([users.c.name]).where(
            users.c.id == uid)
        default_name = await conn.scalar(query)
        parts = default_name.split(".") + [""]

    name = body.get('first_name', parts[0]) + "." + body.get('last_name', parts[1])

    async with engine.acquire() as conn:
        query = (users.update()
                    .where(users.c.id == uid)
                    .values(name=name)
                )
        resp = await conn.execute(query)
        assert resp.rowcount == 1

    raise web.HTTPNoContent(content_type='application/json')


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
            user_id=uid,
            token_service=body['service'],
            token_data=body)
        await conn.execute(stmt)

        raise web.HTTPCreated(text=json.dumps({'data': body}),
                              content_type="application/json")


@login_required
async def list_tokens(request: web.Request):
    await check_permission(request, "user.tokens.*")

    # TODO: start = request.match_info.get('start', 0)
    # TODO: count = request.match_info.get('count', None)
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    user_tokens = []
    async with engine.acquire() as conn:
        query = (sa.select([tokens.c.token_data])
                   .where(tokens.c.user_id == uid)
                 )
        async for row in conn.execute(query):
            user_tokens.append(row["token_data"])

    return user_tokens


@login_required
async def get_token(request: web.Request):
    await check_permission(request, "user.tokens.*")

    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    service_id = request.match_info['service']

    async with engine.acquire() as conn:
        query = (sa.select([tokens.c.token_data])
                   .where(sql.and_(
                       tokens.c.user_id == uid,
                       tokens.c.token_service == service_id) )
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
    service_id = request.match_info['service']

    # TODO: validate
    body = await request.json()

    # TODO: optimize to a single call?
    async with engine.acquire() as conn:
        query = (sa.select([tokens.c.token_data, tokens.c.token_id])
                   .where(sql.and_(
                       tokens.c.user_id == uid,
                       tokens.c.token_service == service_id) )
        )
        result = await conn.execute(query)
        row = await result.first()

        data = dict(row["token_data"])
        tid = row["token_id"]
        data.update(body)

        query = (tokens.update()
                       .where(tokens.c.token_id == tid )
                       .values(token_data=data)
        )
        resp = await conn.execute(query)
        assert resp.rowcount == 1

    raise web.HTTPNoContent(content_type='application/json')

@login_required
async def delete_token(request: web.Request):
    await check_permission(request, "user.tokens.*")

    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    service_id = request.match_info.get('service')

    async with engine.acquire() as conn:
        query = tokens.delete().where(sql.and_(tokens.c.user_id == uid,
                                               tokens.c.token_service == service_id)
                                      )
        await conn.execute(query)

    raise web.HTTPNoContent(content_type='application/json')
