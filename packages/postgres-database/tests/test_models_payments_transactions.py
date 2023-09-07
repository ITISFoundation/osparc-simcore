# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
import decimal
from collections.abc import Callable
from typing import Any

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from pytest_simcore.helpers.rawdata_fakers import FAKE
from simcore_postgres_database.models.payments_transactions import payments_transactions


def utcnow() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def random_payment_transaction(
    **overrides,
) -> dict[str, Any]:
    """Generates Metadata + concept/info (excludes state)"""
    data = {
        "payment_id": FAKE.uuid4(),
        "price_dollars": "123456.78",
        "osparc_credits": "123456.78",
        "product_name": "osparc",
        "user_id": FAKE.pyint(),
        "user_email": FAKE.email().lower(),
        "wallet_id": 1,
        "comment": "Free starting credits",
        "initiated_at": utcnow(),
    }
    # state is not added on purpose
    assert set(data.keys()).issubset({c.name for c in payments_transactions.columns})

    data.update(overrides)
    return data


async def test_numerics_precission_and_scale(connection: SAConnection):
    # https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Numeric
    # precision: This parameter specifies the total number of digits that can be stored, both before and after the decimal point.
    # scale: This parameter specifies the number of digits that can be stored to the right of the decimal point.

    for order_of_magnitude in range(0, 8):
        expected = 10**order_of_magnitude + 0.123
        got = await connection.scalar(
            payments_transactions.insert()
            .values(**random_payment_transaction(price_dollars=expected))
            .returning(payments_transactions.c.price_dollars)
        )
        assert isinstance(got, decimal.Decimal)
        assert float(got) == expected


@pytest.fixture
def init_transaction(connection: SAConnection):
    async def _init(payment_id: str):
        # get payment_id from payment-gateway
        data = random_payment_transaction(payment_id=payment_id)

        # init successful: set timestamp
        data["initiated_at"] = utcnow()

        # insert
        await connection.execute(payments_transactions.insert().values(data))
        return data

    return _init


async def test_create_transaction(connection: SAConnection, init_transaction: Callable):
    payment_id = "5495BF38-4A98-430C-A028-19E4585ADFC7"
    data = await init_transaction(payment_id)
    assert data["payment_id"] == payment_id

    # insert
    result = await connection.execute(
        sa.select(
            payments_transactions.c.completed_at,
            payments_transactions.c.success,
            payments_transactions.c.errors,
        ).where(payments_transactions.c.payment_id == payment_id)
    )
    row: RowProxy | None = await result.fetchone()
    assert row is not None

    # tests that defaults are right?
    assert dict(row.items()) == {
        "completed_at": None,
        "success": None,
        "errors": None,
    }


async def test_complete_transaction_with_success(
    connection: SAConnection, init_transaction: Callable
):
    payment_id = "5495BF38-4A98-430C-A028-19E4585ADFC7"
    await init_transaction(payment_id)

    errors = await connection.scalar(
        payments_transactions.update()
        .values(
            completed_at=utcnow(),
            success=True,
        )
        .where(payments_transactions.c.payment_id == payment_id)
        .returning(payments_transactions.c.errors)
    )
    assert errors is None


async def test_complete_transaction_with_failure(
    connection: SAConnection, init_transaction: Callable
):
    payment_id = "5495BF38-4A98-430C-A028-19E4585ADFC7"
    await init_transaction(payment_id)

    data = await (
        await connection.execute(
            payments_transactions.update()
            .values(
                completed_at=utcnow(),
                success=False,
                errors="some error message",
            )
            .where(payments_transactions.c.payment_id == payment_id)
            .returning(sa.literal_column("*"))
        )
    ).fetchone()

    assert data is not None
    assert data["completed_at"]
    assert not data["success"]
    assert data["errors"] is not None
