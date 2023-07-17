# pylint: disable=E1120

import json
import random
from functools import reduce

import sqlalchemy as sa
from servicelib.common_aiopg_utils import DSN
from simcore_service_webserver.db.models import metadata, tokens, users
from simcore_service_webserver.login.utils import get_random_string
from sqlalchemy import JSON, String, cast
from sqlalchemy.sql import and_  # , or_, not_


def create_db_tables(**kargs):
    url = DSN.format(**kargs)
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    metadata.create_all(bind=engine, tables=[users, tokens], checkfirst=True)
    engine.dispose()
    return url


async def create_token_in_db(engine, **data):
    # TODO change by faker?
    params = {
        "user_id": random.randint(0, 3),
        "token_service": get_random_string(5),
        "token_data": {
            "token_secret": get_random_string(3),
            "token_key": get_random_string(4),
        },
    }
    params.update(data)

    async with engine.acquire() as conn:
        stmt = tokens.insert().values(**params)
        result = await conn.execute(stmt)
        row = await result.first()
        return dict(row)


async def get_token_from_db(
    engine, *, token_id=None, user_id=None, token_service=None, token_data=None
):
    async with engine.acquire() as conn:
        expr = to_expression(
            token_id=token_id,
            user_id=user_id,
            token_service=token_service,
            token_data=token_data,
        )
        stmt = sa.select(tokens).where(expr)
        result = await conn.execute(stmt)
        row = await result.first()
        return dict(row) if row else None


async def delete_token_from_db(engine, *, token_id):
    expr = tokens.c.token_id == token_id
    async with engine.acquire() as conn:
        stmt = tokens.delete().where(expr)
        await conn.execute(stmt)


async def delete_all_tokens_from_db(engine):
    async with engine.acquire() as conn:
        await conn.execute(tokens.delete())


def to_expression(**params):
    expressions = []
    for key, value in params.items():
        if value is not None:
            statement = (
                (cast(getattr(tokens.c, key), String) == json.dumps(value))
                if isinstance(getattr(tokens.c, key).type, JSON)
                else (getattr(tokens.c, key) == value)
            )
            expressions.append(statement)
    return reduce(and_, expressions)
