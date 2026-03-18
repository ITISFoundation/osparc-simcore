# pylint: disable=E1120

import json
from functools import reduce

import sqlalchemy as sa
from servicelib.utils_secrets import generate_password
from simcore_service_webserver.db.models import tokens
from sqlalchemy import JSON, String, cast
from sqlalchemy.sql import and_  # , or_, not_

from .faker_factories import DEFAULT_FAKER


async def create_token_in_db(engine, **data):
    params = {
        "user_id": DEFAULT_FAKER.pyint(),
        "token_service": generate_password(5),
        "token_data": {
            "token_secret": generate_password(3),
            "token_key": generate_password(4),
        },
    }
    params.update(data)

    async with engine.begin() as conn:
        stmt = tokens.insert().values(**params)
        await conn.execute(stmt)


async def get_token_from_db(engine, *, token_id=None, user_id=None, token_service=None, token_data=None):
    async with engine.connect() as conn:
        expr = to_expression(
            token_id=token_id,
            user_id=user_id,
            token_service=token_service,
            token_data=token_data,
        )
        stmt = sa.select(tokens).where(expr)
        result = await conn.execute(stmt)
        row = result.mappings().one_or_none()
        return dict(row) if row else None


async def delete_token_from_db(engine, *, token_id):
    expr = tokens.c.token_id == token_id
    async with engine.begin() as conn:
        stmt = tokens.delete().where(expr)
        await conn.execute(stmt)


async def delete_all_tokens_from_db(engine):
    async with engine.begin() as conn:
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
