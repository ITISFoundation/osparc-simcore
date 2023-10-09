# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
from typing import Any

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import FAKE
from simcore_postgres_database import errors
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from simcore_postgres_database.utils_payments_autorecharge import AutoRechargeStmt


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def _random_payment_method(
    **overrides,
) -> dict[str, Any]:
    data = {
        "payment_method_id": FAKE.uuid4(),
        "user_id": FAKE.pyint(),
        "wallet_id": FAKE.pyint(),
        "initiated_at": _utcnow(),
    }
    # state is not added on purpose
    assert set(data.keys()).issubset({c.name for c in payments_methods.columns})

    data.update(overrides)
    return data


@pytest.fixture
def payment_method_id(faker: Faker) -> str:
    return "5495BF38-4A98-430C-A028-19E4585ADFC7"


async def test_create_payment_method(
    connection: SAConnection,
    payment_method_id: str,
):
    init_values = _random_payment_method(payment_method_id=payment_method_id)
    await connection.execute(payments_methods.insert().values(**init_values))

    # unique payment_method_id
    with pytest.raises(UniqueViolation) as err_info:
        await connection.execute(payments_methods.insert().values(**init_values))
    error = err_info.value
    assert "payment_method_id" in f"{error}"

    # Create payment-method for another entity
    for n in range(2):
        # every user has its own wallet
        wallet_id = init_values["wallet_id"] + n
        user_id = init_values["user_id"] + n
        for _ in range(3):  # payments to wallet_id by user_id
            await connection.execute(
                payments_methods.insert().values(
                    **_random_payment_method(wallet_id=wallet_id, user_id=user_id)
                )
            )

    # list payment methods in wallet_id (user_id)
    result = await connection.execute(
        sa.select(payments_methods).where(
            (payments_methods.c.wallet_id == init_values["wallet_id"])
            & (
                payments_methods.c.user_id == init_values["user_id"]
            )  # ensures ownership
            & (payments_methods.c.state == InitPromptAckFlowState.PENDING)
        )
    )
    rows = await result.fetchall()
    assert rows
    assert len(rows) == 1 + 3

    # get payment-method wallet_id / payment_method_id
    result = await connection.execute(
        sa.select(payments_methods).where(
            (payments_methods.c.payment_method_id == init_values["payment_method_id"])
            & (payments_methods.c.wallet_id == init_values["wallet_id"])
        )
    )
    row: RowProxy | None = await result.fetchone()
    assert row is not None

    # a payment-method added by a user and associated to a wallet


#
# auto-recharge
#


async def _get_auto_recharge(connection, wallet_id) -> RowProxy | None:
    # has recharge trigger?
    stmt = AutoRechargeStmt.get_wallet_autorecharge(wallet_id)
    result = await connection.execute(stmt)
    return await result.first()


async def _is_valid_payment_method(
    connection, user_id, wallet_id, payment_method_id
) -> bool:

    stmt = AutoRechargeStmt.is_valid_payment_method(
        user_id, wallet_id, payment_method_id
    )
    primary_payment_method_id = await connection.scalar(stmt)
    return primary_payment_method_id == payment_method_id


async def _upsert_autorecharge(
    connection,
    wallet_id,
    primary_payment_method_id,
    min_balance_in_usd,
    top_up_amount_in_usd,
    top_up_countdown,
) -> RowProxy:
    # using this primary payment-method, create an autorecharge
    # NOTE: requires the entire
    stmt = AutoRechargeStmt.upsert_wallet_autorecharge(
        wallet_id,
        primary_payment_method_id,
        min_balance_in_usd,
        top_up_amount_in_usd,
        top_up_countdown,
    )
    row = await (await connection.execute(stmt)).first()
    assert row
    return row


async def _update_autorecharge(connection, wallet_id, **settings) -> int | None:
    stmt = AutoRechargeStmt.update_wallet_autorecharge(wallet_id, **settings)
    return await connection.scalar(stmt)


async def _decrease_countdown(connection, wallet_id) -> int | None:
    stmt = AutoRechargeStmt.decrease_wallet_autorecharge_countdown(wallet_id)
    # updates payments countdown
    return await connection.scalar(stmt)


@pytest.mark.testit()
async def test_payments_automation(
    connection: SAConnection,
    payment_method_id: str,
):
    raw_payment_method = _random_payment_method(
        payment_method_id=payment_method_id,
        initiated_at=_utcnow(),
        completed_at=_utcnow() + datetime.timedelta(seconds=1),
        state=InitPromptAckFlowState.SUCCESS,
    )
    result = await connection.execute(
        payments_methods.insert()
        .values(**raw_payment_method)
        .returning(sa.literal_column("*"))
    )
    row = await result.first()
    assert row
    assert row.payment_method_id == payment_method_id
    wallet_id = row.wallet_id
    user_id = row.user_id

    assert _is_valid_payment_method(connection, user_id, wallet_id, payment_method_id)

    #
    #
    #

    # get
    auto_recharge = await _get_auto_recharge(connection, wallet_id)
    assert auto_recharge is None

    # new
    await _upsert_autorecharge(
        connection,
        wallet_id,
        primary_payment_method_id=payment_method_id,
        min_balance_in_usd=10,
        top_up_amount_in_usd=100,
        top_up_countdown=5,
    )

    auto_recharge = await _get_auto_recharge(connection, wallet_id)
    assert auto_recharge is not None
    assert auto_recharge.primary_payment_method_id == payment_method_id

    await _upsert_autorecharge(
        connection,
        wallet_id,
        primary_payment_method_id=payment_method_id,
        min_balance_in_usd=2.50,
        top_up_amount_in_usd=100,
        top_up_countdown=None,
    )

    # countdown
    assert await _decrease_countdown(connection, wallet_id) == 4
    assert await _decrease_countdown(connection, wallet_id) == 3
    assert await _decrease_countdown(connection, wallet_id) == 2
    assert await _decrease_countdown(connection, wallet_id) == 1
    assert await _decrease_countdown(connection, wallet_id) == 0

    with pytest.raises(errors.CheckViolation) as err_info:
        await _decrease_countdown(connection, wallet_id)

    exc = err_info.value
    assert exc.pgerror
    assert "check_top_up_countdown_nonnegative" in exc.pgerror

    # deactivate countdown
    await _update_autorecharge(connection, wallet_id, inc_payments_countdown=None)
    assert await _decrease_countdown(connection, wallet_id) is None

    # change primary-payment-method

    # list payment-methods and mark if primary or not
