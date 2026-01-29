# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
import sqlalchemy as sa
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_payment_method
from pytest_simcore.helpers.postgres_products import insert_and_get_product_lifespan
from pytest_simcore.helpers.postgres_users import (
    insert_and_get_user_and_secrets_lifespan,
)
from pytest_simcore.helpers.postgres_wallets import insert_and_get_wallet_lifespan
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def payment_method_id(faker: Faker) -> str:
    return "5495BF38-4A98-430C-A028-19E4585ADFC7"


async def test_create_payment_method(
    asyncpg_engine: AsyncEngine,
    payment_method_id: str,
):
    async with (
        insert_and_get_user_and_secrets_lifespan(asyncpg_engine) as user_row,
        insert_and_get_product_lifespan(asyncpg_engine) as product_row,
        insert_and_get_wallet_lifespan(
            asyncpg_engine,
            product_name=product_row["name"],
            user_group_id=user_row["primary_gid"],
        ) as wallet_row,
    ):
        # Insert initial payment method
        async with asyncpg_engine.begin() as connection:
            init_values = random_payment_method(
                payment_method_id=payment_method_id,
                user_id=user_row["id"],
                wallet_id=wallet_row["wallet_id"],
            )
            await connection.execute(payments_methods.insert().values(**init_values))

        # unique payment_method_id - should fail in a separate transaction
        async with asyncpg_engine.begin() as connection:
            with pytest.raises(sa.exc.IntegrityError) as err_info:
                await connection.execute(payments_methods.insert().values(**init_values))
            assert "payment_method_id" in str(err_info.value)

        # Create payment-method for another entity
        for _ in range(2):
            # Create additional users and wallets
            async with (
                insert_and_get_user_and_secrets_lifespan(asyncpg_engine) as other_user_row,
                insert_and_get_wallet_lifespan(
                    asyncpg_engine,
                    product_name=product_row["name"],
                    user_group_id=other_user_row["primary_gid"],
                ) as other_wallet_row,
                asyncpg_engine.begin() as connection,
            ):
                for _ in range(3):  # payments to wallet_id by user_id
                    await connection.execute(
                        payments_methods.insert().values(
                            **random_payment_method(
                                wallet_id=other_wallet_row["wallet_id"],
                                user_id=other_user_row["id"],
                            )
                        )
                    )

        # list payment methods in wallet_id (user_id)
        async with asyncpg_engine.begin() as connection:
            result = await connection.execute(
                sa.select(payments_methods).where(
                    (payments_methods.c.wallet_id == init_values["wallet_id"])
                    & (payments_methods.c.user_id == init_values["user_id"])  # ensures ownership
                    & (payments_methods.c.state == InitPromptAckFlowState.PENDING)
                )
            )
            rows = result.all()
            assert rows
            assert len(rows) == 1

            # get payment-method wallet_id / payment_method_id
            result = await connection.execute(
                sa.select(payments_methods).where(
                    (payments_methods.c.payment_method_id == init_values["payment_method_id"])
                    & (payments_methods.c.wallet_id == init_values["wallet_id"])
                )
            )
            row = result.one_or_none()
            assert row is not None

            # a payment-method added by a user and associated to a wallet
