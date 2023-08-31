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
        "prize_dollars": "123456.78",
        "osparc_credits": "123456.78",
        "product_name": "osparc",
        "user_id": FAKE.pyint(),
        "user_email": FAKE.email().lower(),
        "wallet_id": 1,
        "wallet_name": "user wallet",
        "comment": "Free starting credits",
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
            .values(**random_payment_transaction(prize_dollars=expected))
            .returning(payments_transactions.c.prize_dollars)
        )
        assert isinstance(got, decimal.Decimal)
        # TODO: not sure about Decimal user
        # TODO: review https://docs.python.org/3/library/decimal.html#quick-start-tutorial

        assert float(got) == expected


@pytest.fixture
def init_transaction(connection: SAConnection):
    async def _init(payment_id: str):
        # get payment_id from payment-gateway
        data = random_payment_transaction(payment_id=payment_id)

        # init successful: set timestamp
        data["initiated"] = utcnow()

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
            payments_transactions.c.completed,
            payments_transactions.c.success,
            payments_transactions.c.errors,
        ).where(payments_transactions.c.payment_id == payment_id)
    )
    row: RowProxy | None = await result.fetchone()
    assert row is not None

    # defaults are right?
    assert dict(row.items()) == {
        "completed": None,
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
        .values(completed=True, success=True)
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
            .values(completed=True, success=False, error="some error message")
            .where(payments_transactions.c.payment_id == payment_id)
            .returning(sa.literal_column("*"))
        )
    ).fetchone()

    assert data is not None
    assert data["completed"]
    assert not data["success"]
    assert data["error"] is not None


async def test_detect_incompleted_transactions_after_timeout():
    ...


async def test_list_user_transactions():
    ...
