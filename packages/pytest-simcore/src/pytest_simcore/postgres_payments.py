import contextlib

from simcore_postgres_database.models.payments_autorecharge import payments_autorecharge
from simcore_postgres_database.models.payments_methods import payments_methods
from simcore_postgres_database.models.payments_transactions import payments_transactions
from sqlalchemy.ext.asyncio import AsyncEngine

from .helpers.faker_factories import (
    random_payment_autorecharge,
    random_payment_method,
    random_payment_transaction,
)
from .postgres_tools import (
    insert_and_get_row_lifespan,
)


@contextlib.asynccontextmanager
async def insert_and_get_payment_method_lifespan(
    sqlalchemy_async_engine: AsyncEngine, *, user_id: int, wallet_id: int, **overrides
):
    async with contextlib.AsyncExitStack() as stack:
        output = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=payments_methods,
                values=random_payment_method(
                    user_id=user_id, wallet_id=wallet_id, **overrides
                ),
                pk_col=payments_methods.c.payment_method_id,
            )
        )

        yield output


@contextlib.asynccontextmanager
async def insert_and_get_payment_auto_recharge_lifespan(
    sqlalchemy_async_engine: AsyncEngine,
    *,
    payment_method_id: str,
    wallet_id: int,
    **overrides
):
    async with contextlib.AsyncExitStack() as stack:
        output = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=payments_autorecharge,
                values=random_payment_autorecharge(
                    payment_method_id=payment_method_id,
                    wallet_id=wallet_id,
                    **overrides
                ),
                pk_col=payments_autorecharge.c.id,
            )
        )

        yield output


@contextlib.asynccontextmanager
async def insert_and_get_payment_transaction_lifespan(
    sqlalchemy_async_engine: AsyncEngine,
    *,
    product_name: str,
    user_id: int,
    wallet_id: int,
    **overrides
):
    async with contextlib.AsyncExitStack() as stack:
        output = await stack.enter_async_context(
            insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
                sqlalchemy_async_engine,
                table=payments_transactions,
                values=random_payment_transaction(
                    product_name=product_name,
                    user_id=user_id,
                    wallet_id=wallet_id,
                    **overrides
                ),
                pk_col=payments_transactions.c.payment_id,
            )
        )

        yield output
