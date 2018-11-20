# pylint: disable=E1120

import random

import sqlalchemy as sa
from aiohttp import web

from simcore_service_webserver.db import APP_DB_ENGINE_KEY
from simcore_service_webserver.db_models import metadata, tokens, users
from simcore_service_webserver.login.utils import get_random_string


def create_tables(url):
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, tables=[users, tokens], checkfirst=True)

async def create_token(engine, data=None):
    data = data or {}
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
        return (await conn.execute(stmt))



class NewToken:
    def __init__(self, params=None, app: web.Application = None):
        self.params = params
        self.token = None
        self.engine = app[APP_DB_ENGINE_KEY]

    async def __aenter__(self):
        self.token = await create_token(self.engine, self.params)
        return self.token

    async def __aexit__(self, *args):
        async with self.engine.acquire() as conn:
            stmt = tokens.delete().where(self.token)
            await conn.execute(stmt)
            self.token = None


    # Tests read profile --------------------------------------------
