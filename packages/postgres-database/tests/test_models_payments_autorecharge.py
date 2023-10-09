# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import datetime
from typing import TypeAlias

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import random_payment_method, utcnow
from simcore_postgres_database import errors
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from simcore_postgres_database.utils_payments_autorecharge import AutoRechargeStmt

#
# HELPERS
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


PaymentMethodRow: TypeAlias = RowProxy


@pytest.fixture
async def payment_method(connection: SAConnection, faker: Faker) -> PaymentMethodRow:
    payment_method_id = faker.uuid4().upper()

    raw_payment_method = random_payment_method(
        payment_method_id=payment_method_id,
        initiated_at=utcnow(),
        completed_at=utcnow() + datetime.timedelta(seconds=1),
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

    assert await _is_valid_payment_method(
        connection, user_id, wallet_id, payment_method_id
    )
    return row


async def test_payments_automation_workflow(
    connection: SAConnection, payment_method: PaymentMethodRow
):
    payment_method_id = payment_method.payment_method_id
    wallet_id = payment_method.wallet_id

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

    # upsert: deactivate countdown
    auto_recharge = await _upsert_autorecharge(
        connection,
        wallet_id,
        primary_payment_method_id=payment_method_id,
        min_balance_in_usd=10,
        top_up_amount_in_usd=100,
        top_up_countdown=None,  # <----
    )
    assert auto_recharge.top_up_countdown is None

    await _update_autorecharge(connection, wallet_id, top_up_countdown=None)
    assert await _decrease_countdown(connection, wallet_id) is None
