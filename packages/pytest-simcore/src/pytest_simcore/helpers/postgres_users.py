import contextlib

import sqlalchemy as sa
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from simcore_postgres_database.models.users_secrets import users_secrets
from sqlalchemy.dialects import postgresql
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
    if "product_name" in user_kwargs:
        secrets_kwargs["product_name"] = user_kwargs.pop("product_name")
    return user_kwargs, secrets_kwargs


async def _ensure_product_exists(conn, product_name: str) -> None:
    # NOTE: users_secrets.product_name is a FK to products.name. Test databases created
    # via metadata.create_all() (as opposed to running the actual migrations) do not have
    # the 'osparc' product seeded, so it is idempotently created here on demand.
    await conn.execute(
        postgresql.insert(products)
        .values(name=product_name, host_regex=".*", base_url="https://example.com")
        .on_conflict_do_nothing(index_elements=["name"])
    )


def _sync_ensure_product_exists(conn, product_name: str) -> None:
    conn.execute(
        postgresql.insert(products)
        .values(name=product_name, host_regex=".*", base_url="https://example.com")
        .on_conflict_do_nothing(index_elements=["name"])
    )


@contextlib.asynccontextmanager
async def insert_and_get_user_and_secrets_lifespan(sqlalchemy_async_engine: AsyncEngine, **overrides):
    user_kwargs, secrets_kwargs = _get_kwargs_from_overrides(overrides)

    async with contextlib.AsyncExitStack() as stack:
        # users
        user = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=users,
                values=random_user(**user_kwargs),
                pk_col=users.c.id,
            )
        )

        secrets_values = random_user_secrets(user_id=user["id"], **secrets_kwargs)
        async with sqlalchemy_async_engine.begin() as conn:
            await _ensure_product_exists(conn, secrets_values["product_name"])

        # users_secrets
        secrets = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=users_secrets,
                values=secrets_values,
                pk_cols=[users_secrets.c.user_id, users_secrets.c.product_name],
            )
        )

        assert secrets.pop("user_id", None) == user["id"]

        yield {**user, **secrets}


@contextlib.contextmanager
def sync_insert_and_get_user_and_secrets_lifespan(sqlalchemy_sync_engine: sa.engine.Engine, **overrides):
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

        secrets_values = random_user_secrets(user_id=user["id"], **secrets_kwargs)
        with sqlalchemy_sync_engine.begin() as conn:
            _sync_ensure_product_exists(conn, secrets_values["product_name"])

        # users_secrets
        secrets = stack.enter_context(
            sync_insert_and_get_row_lifespan(
                sqlalchemy_sync_engine,
                table=users_secrets,
                values=secrets_values,
                pk_cols=[users_secrets.c.user_id, users_secrets.c.product_name],
            )
        )

        assert secrets.pop("user_id", None) == user["id"]

        yield {**user, **secrets}


async def insert_user_and_secrets(conn, **overrides) -> int:
    # NOTE: DEPRECATED: Legacy adapter. Use insert_and_get_user_and_secrets_lifespan instead

    user_kwargs, secrets_kwargs = _get_kwargs_from_overrides(overrides)

    # user data
    user_id = await conn.scalar(users.insert().values(**random_user(**user_kwargs)).returning(users.c.id))
    assert user_id is not None

    # secrets
    secrets_values = random_user_secrets(user_id=user_id, **secrets_kwargs)
    await _ensure_product_exists(conn, secrets_values["product_name"])
    await conn.execute(users_secrets.insert().values(**secrets_values))

    return user_id
