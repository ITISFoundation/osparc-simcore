# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unexpected-keyword-arg
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import decimal
from collections.abc import Callable
from typing import Any

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from pytest_simcore.helpers.faker_factories import random_payment_transaction, utcnow
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
    payments_transactions,
)
from simcore_postgres_database.utils_payments import (
    PaymentAlreadyAcked,
    PaymentNotFound,
    PaymentTransactionRow,
    get_user_payments_transactions,
    insert_init_payment_transaction,
    update_payment_transaction_state,
)


async def test_numerics_precission_and_scale(connection: SAConnection):
    # https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Numeric
    # precision: This parameter specifies the total number of digits that can be stored, both before and after the decimal point.
    # scale: This parameter specifies the number of digits that can be stored to the right of the decimal point.

    for order_of_magnitude in range(8):
        expected = 10**order_of_magnitude + 0.123
        got = await connection.scalar(
            payments_transactions.insert()
            .values(**random_payment_transaction(price_dollars=expected))
            .returning(payments_transactions.c.price_dollars)
        )
        assert isinstance(got, decimal.Decimal)
        assert float(got) == expected


def _remove_not_required(data: dict[str, Any]) -> dict[str, Any]:
    for to_remove in (
        "completed_at",
        "invoice_url",
        "invoice_pdf_url",
        "state",
        "state_message",
        "stripe_invoice_id",
    ):
        data.pop(to_remove)
    return data


@pytest.fixture
def init_transaction(connection: SAConnection):
    async def _init(payment_id: str):
        # get payment_id from payment-gateway
        values = _remove_not_required(random_payment_transaction(payment_id=payment_id))

        # init successful: set timestamp
        values["initiated_at"] = utcnow()

        # insert
        ok = await insert_init_payment_transaction(connection, **values)
        assert ok

        return values

    return _init


@pytest.fixture
def payment_id() -> str:
    return "5495BF38-4A98-430C-A028-19E4585ADFC7"


async def test_init_transaction_sets_it_as_pending(
    connection: SAConnection, init_transaction: Callable, payment_id: str
):
    values = await init_transaction(payment_id)
    assert values["payment_id"] == payment_id

    # check init-ed but not completed!
    result = await connection.execute(
        sa.select(
            payments_transactions.c.completed_at,
            payments_transactions.c.state,
            payments_transactions.c.state_message,
        ).where(payments_transactions.c.payment_id == payment_id)
    )
    row: RowProxy | None = await result.fetchone()
    assert row is not None

    # tests that defaults are right?
    assert dict(row.items()) == {
        "completed_at": None,
        "state": PaymentTransactionState.PENDING,
        "state_message": None,
    }


@pytest.fixture
def invoice_url(faker: Faker, expected_state: PaymentTransactionState) -> str | None:
    if expected_state == PaymentTransactionState.SUCCESS:
        return faker.url()
    return None


@pytest.mark.parametrize(
    "expected_state,expected_message",
    [
        (
            state,
            None if state is PaymentTransactionState.SUCCESS else f"with {state}",
        )
        for state in [
            PaymentTransactionState.SUCCESS,
            PaymentTransactionState.FAILED,
            PaymentTransactionState.CANCELED,
        ]
    ],
)
async def test_complete_transaction(
    connection: SAConnection,
    init_transaction: Callable,
    payment_id: str,
    expected_state: PaymentTransactionState,
    expected_message: str | None,
    invoice_url: str | None,
):
    await init_transaction(payment_id)

    payment_row = await update_payment_transaction_state(
        connection,
        payment_id=payment_id,
        completion_state=expected_state,
        state_message=expected_message,
        invoice_url=invoice_url,
    )

    assert isinstance(payment_row, PaymentTransactionRow)
    assert payment_row.state_message == expected_message
    assert payment_row.state == expected_state
    assert payment_row.initiated_at < payment_row.completed_at
    assert PaymentTransactionState(payment_row.state).is_completed()


async def test_update_transaction_failures_and_exceptions(
    connection: SAConnection,
    init_transaction: Callable,
    payment_id: str,
):
    kwargs = {
        "connection": connection,
        "payment_id": payment_id,
        "completion_state": PaymentTransactionState.SUCCESS,
    }

    ok = await update_payment_transaction_state(**kwargs)
    assert isinstance(ok, PaymentNotFound)
    assert not ok

    # init & complete
    await init_transaction(payment_id)
    ok = await update_payment_transaction_state(**kwargs)
    assert isinstance(ok, PaymentTransactionRow)
    assert ok

    # repeat -> fails
    ok = await update_payment_transaction_state(**kwargs)
    assert isinstance(ok, PaymentAlreadyAcked)
    assert not ok

    with pytest.raises(ValueError):
        kwargs.update(completion_state=PaymentTransactionState.PENDING)
        await update_payment_transaction_state(**kwargs)


@pytest.fixture
def user_id() -> int:
    return 1


@pytest.fixture
def create_fake_user_transactions(connection: SAConnection, user_id: int) -> Callable:
    async def _go(expected_total=5):
        payment_ids = []
        for _ in range(expected_total):
            values = _remove_not_required(random_payment_transaction(user_id=user_id))

            payment_id = await insert_init_payment_transaction(connection, **values)
            assert payment_id
            payment_ids.append(payment_id)

        return payment_ids

    return _go


async def test_get_user_payments_transactions(
    connection: SAConnection, create_fake_user_transactions: Callable, user_id: int
):
    expected_payments_ids = await create_fake_user_transactions()
    expected_total = len(expected_payments_ids)

    # test offset and limit defaults
    total, rows = await get_user_payments_transactions(connection, user_id=user_id)
    assert total == expected_total
    assert [r.payment_id for r in rows] == expected_payments_ids[::-1], "newest first"


async def test_get_user_payments_transactions_with_pagination_options(
    connection: SAConnection, create_fake_user_transactions: Callable, user_id: int
):
    expected_payments_ids = await create_fake_user_transactions()
    expected_total = len(expected_payments_ids)

    # test  offset, limit
    offset = int(expected_total / 4)
    limit = int(expected_total / 2)

    total, rows = await get_user_payments_transactions(
        connection, user_id=user_id, limit=limit, offset=offset
    )
    assert total == expected_total
    assert [r.payment_id for r in rows] == expected_payments_ids[::-1][
        offset : (offset + limit)
    ], "newest first"

    # test  offset>=expected_total?
    total, rows = await get_user_payments_transactions(
        connection, user_id=user_id, offset=expected_total
    )
    assert not rows

    # test  limit==0?
    total, rows = await get_user_payments_transactions(
        connection, user_id=user_id, limit=0
    )
    assert not rows
