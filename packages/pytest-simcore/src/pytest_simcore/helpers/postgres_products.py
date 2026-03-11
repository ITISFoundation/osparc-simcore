import contextlib

from simcore_postgres_database.models.products import products
from sqlalchemy.ext.asyncio import AsyncEngine

from .faker_factories import random_product
from .postgres_tools import (
    insert_and_get_row_lifespan,
)


@contextlib.asynccontextmanager
async def insert_and_get_product_lifespan(sqlalchemy_async_engine: AsyncEngine, **overrides):
    async with contextlib.AsyncExitStack() as stack:
        # wallets
        product = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=products,
                values=random_product(**overrides),
                pk_col=products.c.name,
            )
        )

        yield product
