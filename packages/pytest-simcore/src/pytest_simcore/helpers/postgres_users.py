import contextlib

from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_secrets import users_secrets
from sqlalchemy.ext.asyncio import AsyncEngine

from .faker_factories import random_user, random_user_secrets
from .postgres_tools import insert_and_get_row_lifespan


@contextlib.asynccontextmanager
async def insert_and_get_user_and_secrets_lifespan(
    sqlalchemy_async_engine: AsyncEngine, **overrides
):

    password = overrides.pop("password", None)

    async with contextlib.AsyncExitStack() as stack:
        # users
        user = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=users,
                values=random_user(**random_user(**overrides)),
                pk_col=users.c.id,
            )
        )

        # users_secrets
        user_secret = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=users_secrets,
                values=random_user_secrets(user_id=user["id"], password=password),
                pk_col=users.c.id,
            )
        )

        yield {**user, "password_hash": user_secret["password_hash"]}


async def insert_user_and_secrets(conn, **overrides) -> int:
    # NOTE: Legacy adapter. Use insert_and_get_user_and_secrets_lifespan instead

    password = overrides.pop("password", None)
    # user data
    user_id = await conn.scalar(
        users.insert().values(**random_user(**overrides)).returning(users.c.id)
    )
    assert user_id is not None

    # secrets
    await conn.execute(
        users_secrets.insert().values(
            **random_user_secrets(user_id=user_id, password=password)
        )
    )

    return user_id
