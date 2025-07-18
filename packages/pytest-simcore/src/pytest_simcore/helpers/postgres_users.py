import contextlib

import sqlalchemy as sa
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_secrets import users_secrets
from sqlalchemy.ext.asyncio import AsyncEngine

from .faker_factories import random_user, random_user_secrets
from .postgres_tools import (
    insert_and_get_row_lifespan,
    sync_insert_and_get_row_lifespan,
)


def _get_kwargs_from_overrides(overrides: dict) -> tuple[dict, dict]:
    user_kwargs = overrides.copy()
    secrets_kwargs = {"password": user_kwargs.pop("password", None)}
    if "password_hash" in user_kwargs:
        secrets_kwargs["password_hash"] = user_kwargs.pop("password_hash")
    return user_kwargs, secrets_kwargs


@contextlib.asynccontextmanager
async def insert_and_get_user_and_secrets_lifespan(
    sqlalchemy_async_engine: AsyncEngine, **overrides
):
    user_kwargs, secrets_kwargs = _get_kwargs_from_overrides(overrides)

    async with contextlib.AsyncExitStack() as stack:
        # users
        user = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=users,
                values=random_user(**random_user(**user_kwargs)),
                pk_col=users.c.id,
            )
        )

        # users_secrets
        secrets = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=users_secrets,
                values=random_user_secrets(user_id=user["id"], **secrets_kwargs),
                pk_col=users_secrets.c.user_id,
            )
        )

        assert secrets.pop("user_id", None) == user["id"]

        yield {**user, **secrets}


@contextlib.contextmanager
def sync_insert_and_get_user_and_secrets_lifespan(
    sqlalchemy_sync_engine: sa.engine.Engine, **overrides
):
    user_kwargs, secrets_kwargs = _get_kwargs_from_overrides(overrides)

    with contextlib.ExitStack() as stack:
        # users
        user = stack.enter_context(
            sync_insert_and_get_row_lifespan(
                sqlalchemy_sync_engine,
                table=users,
                values=random_user(**user_kwargs),
                pk_col=users.c.id,
            )
        )

        # users_secrets
        secrets = stack.enter_context(
            sync_insert_and_get_row_lifespan(
                sqlalchemy_sync_engine,
                table=users_secrets,
                values=random_user_secrets(user_id=user["id"], **secrets_kwargs),
                pk_col=users_secrets.c.user_id,
            )
        )

        assert secrets.pop("user_id", None) == user["id"]

        yield {**user, **secrets}


async def insert_user_and_secrets(conn, **overrides) -> int:
    # NOTE: Legacy adapter. Use insert_and_get_user_and_secrets_lifespan instead
    # Temporarily used where conn is produce by aiopg_engine

    user_kwargs, secrets_kwargs = _get_kwargs_from_overrides(overrides)

    # user data
    user_id = await conn.scalar(
        users.insert().values(**random_user(**user_kwargs)).returning(users.c.id)
    )
    assert user_id is not None

    # secrets
    await conn.execute(
        users_secrets.insert().values(
            **random_user_secrets(user_id=user_id, **secrets_kwargs)
        )
    )

    return user_id
