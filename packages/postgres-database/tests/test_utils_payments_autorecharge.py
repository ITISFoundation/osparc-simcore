# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
from collections.abc import AsyncIterable

import pytest
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_payment_method, utcnow
from pytest_simcore.helpers.postgres_products import insert_and_get_product_lifespan
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.postgres_users import (
    insert_and_get_user_and_secrets_lifespan,
)
from pytest_simcore.helpers.postgres_wallets import insert_and_get_wallet_lifespan
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from simcore_postgres_database.utils_payments_autorecharge import AutoRechargeStatements
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

#
# HELPERS
#


async def _get_auto_recharge(connection: AsyncConnection, wallet_id) -> Row | None:
    # has recharge trigger?
    stmt = AutoRechargeStatements.get_wallet_autorecharge(wallet_id)
    result = await connection.execute(stmt)
    return result.first()


async def _is_valid_payment_method(
    connection: AsyncConnection, user_id, wallet_id, payment_method_id
) -> bool:

    stmt = AutoRechargeStatements.is_valid_payment_method(
        user_id, wallet_id, payment_method_id
    )
    primary_payment_method_id = await connection.scalar(stmt)
    return primary_payment_method_id == payment_method_id


async def _upsert_autorecharge(
    connection: AsyncConnection,
    wallet_id,
    enabled,
    primary_payment_method_id,
    top_up_amount_in_usd,
    monthly_limit_in_usd,
) -> Row:
    # using this primary payment-method, create an autorecharge
    # NOTE: requires the entire
    stmt = AutoRechargeStatements.upsert_wallet_autorecharge(
        wallet_id=wallet_id,
        enabled=enabled,
        primary_payment_method_id=primary_payment_method_id,
        top_up_amount_in_usd=top_up_amount_in_usd,
        monthly_limit_in_usd=monthly_limit_in_usd,
    )
    result = await connection.execute(stmt)
    return result.one()


async def _update_autorecharge(
    connection: AsyncConnection, wallet_id, **settings
) -> int | None:
    stmt = AutoRechargeStatements.update_wallet_autorecharge(wallet_id, **settings)
    return await connection.scalar(stmt)


class PaymentMethodRow(dict):
    # Convert dict to Row-like object for compatibility
    def __getattr__(self, key):
        return self[key]


@pytest.fixture
async def payment_method(
    asyncpg_engine: AsyncEngine, faker: Faker
) -> AsyncIterable[PaymentMethodRow]:
    payment_method_id = faker.uuid4().upper()

    async with insert_and_get_user_and_secrets_lifespan(asyncpg_engine) as user_row:
        user_id = user_row["id"]

        async with insert_and_get_product_lifespan(asyncpg_engine) as product_row:
            product_name = product_row["name"]

            async with insert_and_get_wallet_lifespan(
                asyncpg_engine, product_name=product_name, user_id=user_id
            ) as wallet_row:

                raw_payment_method_values = random_payment_method(
                    payment_method_id=payment_method_id,
                    initiated_at=utcnow(),
                    completed_at=utcnow() + datetime.timedelta(seconds=1),
                    state=InitPromptAckFlowState.SUCCESS,
                    user_id=user_id,
                    wallet_id=wallet_row["wallet_id"],
                )

                # pylint: disable=contextmanager-generator-missing-cleanup
                async with insert_and_get_row_lifespan(
                    asyncpg_engine,
                    table=payments_methods,
                    values=raw_payment_method_values,
                    pk_col=payments_methods.c.payment_method_id,
                    pk_value=payment_method_id,
                ) as row_data:
                    wallet_id = row_data["wallet_id"]
                    user_id = row_data["user_id"]

                    async with asyncpg_engine.connect() as connection:
                        assert await _is_valid_payment_method(
                            connection, user_id, wallet_id, payment_method_id
                        )

                    yield PaymentMethodRow(row_data)


async def test_payments_automation_workflow(
    asyncpg_engine: AsyncEngine, payment_method: PaymentMethodRow
):
    payment_method_id = payment_method.payment_method_id
    wallet_id = payment_method.wallet_id

    async with asyncpg_engine.begin() as connection:
        # get
        auto_recharge = await _get_auto_recharge(connection, wallet_id)
        assert auto_recharge is None

        # new
        await _upsert_autorecharge(
            connection,
            wallet_id,
            enabled=True,
            primary_payment_method_id=payment_method_id,
            top_up_amount_in_usd=100,
            monthly_limit_in_usd=None,
        )

        auto_recharge = await _get_auto_recharge(connection, wallet_id)
        assert auto_recharge is not None
        assert auto_recharge.primary_payment_method_id == payment_method_id
        assert auto_recharge.enabled is True

        # upsert: deactivate countdown
        auto_recharge = await _upsert_autorecharge(
            connection,
            wallet_id,
            enabled=True,
            primary_payment_method_id=payment_method_id,
            top_up_amount_in_usd=100,
            monthly_limit_in_usd=10000,  # <----
        )
        assert auto_recharge.monthly_limit_in_usd == 10000

        await _update_autorecharge(connection, wallet_id, monthly_limit_in_usd=None)
