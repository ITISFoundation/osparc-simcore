import contextlib

from simcore_postgres_database.models.wallets import wallets
from sqlalchemy.ext.asyncio import AsyncEngine

from .faker_factories import random_wallet
from .postgres_tools import (
    insert_and_get_row_lifespan,
)


@contextlib.asynccontextmanager
async def insert_and_get_wallet_lifespan(
    sqlalchemy_async_engine: AsyncEngine, *, product_name: str, user_group_id: int, **overrides
):
    async with contextlib.AsyncExitStack() as stack:
        # wallets
        wallet = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=wallets,
                values=random_wallet(product_name=product_name, user_group_id=user_group_id, **overrides),
                pk_col=wallets.c.wallet_id,
            )
        )

        yield wallet
