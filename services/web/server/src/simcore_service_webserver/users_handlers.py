# pylint: disable=no-value-for-parameter

import json
import logging

import sqlalchemy as sa
import sqlalchemy.sql as sql
from aiohttp import web

from servicelib.application_keys import APP_DB_ENGINE_KEY

from .db_models import tokens, users
from .login.decorators import RQT_USERID_KEY, login_required
from .utils import gravatar_hash

logger = logging.getLogger(__name__)


# my/ -----------------------------------------------------------
@login_required
async def get_my_profile(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    async with engine.acquire() as conn:
        stmt = sa.select([users.c.email]).where(users.c.id == uid)
        email = await conn.scalar(stmt)

    return {
        'login': email,
        'gravatar_id': gravatar_hash(email)
    }


# my/tokens/ ------------------------------------------------------
@login_required
async def create_tokens(request: web.Request):
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
        result = await conn.execute(stmt)
        row = await result.first()

        raise web.HTTPCreated(text=json.dumps({'data': row['token_id']}),
                              content_type="application/json")


@login_required
async def list_tokens(request: web.Request):
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


@login_required
async def delete_token(request: web.Request):
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    service_id = request.match_info.get('service')

    async with engine.acquire() as conn:
        query = tokens.delete().where(sql.and_(tokens.c.user_id == uid,
                                               tokens.c.token_service == service_id)
                                      )
        await conn.execute(query)

    raise web.HTTPNoContent(content_type='application/json')
