# pylint: disable=E1120

import random
from functools import reduce

import sqlalchemy as sa
from aiohttp import web
from sqlalchemy.sql import and_  # , or_, not_

from simcore_service_webserver.db import APP_DB_ENGINE_KEY, DSN
from simcore_service_webserver.db_models import metadata, tokens, users
from simcore_service_webserver.login.utils import get_random_string


def create_tables(**kargs):
    url = DSN.format(**kargs)
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, tables=[users, tokens], checkfirst=True)
    return url

async def create_token(engine, **data):
    params = {
        "user_id": random.randint(0, 3),
        "token_service": get_random_string(5),
        "token_data": {
            "token_secret": get_random_string(3),
            "token_key": get_random_string(4),
        }
    }
    params.update(data)

    async with engine.acquire() as conn:
        stmt = tokens.insert().values(**params)
        import pdb; pdb.set_trace()
        return (await conn.execute(stmt))

async def get_token(engine, *, token_id):
    async with engine.acquire() as conn:
        stmt = sa.select([tokens,]).where(
            tokens.c.token_id == token_id
        )
        result = await conn.execute(stmt)
        token = await result.first()
        return dict(token)

async def delete_token(engine, *, token_id):
    expr = tokens.c.token_id == token_id
    async with engine.acquire() as conn:
        stmt = tokens.delete().where(expr)
        await conn.execute(stmt)

async def delete_all_tokens(engine):
    async with engine.acquire() as conn:
        await conn.execute(tokens.delete())

def build_expression(params):
    expr = reduce(and_, [ getattr(tokens.c, key) == value for key, value in params.items() ] )
    return expr




class NewToken:
    def __init__(self, params=None, app: web.Application = None):
        self.params = params
        self.token = None
        self.engine = app[APP_DB_ENGINE_KEY]

    async def __aenter__(self):
        self.token = await create_token(self.engine, **self.params)
        return self.token

    async def __aexit__(self, *args):
        async with self.engine.acquire() as conn:
            stmt = tokens.delete().where(
                tokens.c.token_id == self.token[tokens.c.token_id]
            )
            _result_proxy = await conn.execute(stmt)
            self.token = None


    # Tests read profile --------------------------------------------
