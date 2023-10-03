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
from simcore_postgres_database.errors import UniqueViolation
from simcore_postgres_database.models.payments_automation import payments_automation
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)


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


@pytest.mark.testit
async def test_payments_automation(
    connection: SAConnection,
    payment_method_id: str,
):
    init_values = _random_payment_method(payment_method_id=payment_method_id)
    result = await connection.execute(
        payments_methods.insert().values(**init_values).returning(sa.text("*"))
    )
    payment_method_row = await result.first()
    assert payment_method_row
    assert payment_method_row.payment_method_id == payment_method_id

    # has recharge trigger?
    async def _get_wallet_auto_recharge(w) -> RowProxy | None:
        stmt = (
            sa.select(
                payments_methods.c.wallet_id,
                payments_methods.c.user_id,
                payments_methods.c.payment_method_id,
                payments_automation.c.enabled,
                payments_automation.c.min_balance_in_usd,
                payments_automation.c.inc_payment_amount_in_usd,
                payments_automation.c.inc_payments_countdown,
            )
            .select_from(
                payments_methods.join(
                    payments_automation,
                    payments_methods.c.payment_method_id
                    == payments_automation.c.payment_method_id,
                )
            )
            .where(
                (payments_automation.c.wallet_id == w)
                & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
            )
        )
        result = await connection.execute(stmt)
        return await result.first()

    # using this primary payment-method, create an autorecharge
    async def _create_wallet_autorecharge(pm, th, ip, cd) -> None:
        # TODO: has to be only one valid payment method in the wallet at a time!
        await connection.execute(
            payments_automation.insert().values(
                payment_method_id=pm,
                min_balance_in_usd=th,
                inc_payment_amount_in_usd=ip,
                inc_payments_countdown=cd,
            )
        )

    auto_recharge = await _get_wallet_auto_recharge(payment_method_row.wallet_id)
    assert auto_recharge is None

    await _create_wallet_autorecharge(payment_method_id, th=10, ip=100, cd=5)
    auto_recharge = await _get_wallet_auto_recharge(payment_method_row.wallet_id)
    assert auto_recharge is not None
    assert auto_recharge.payment_method_id == payment_method_id

    # updates payments countdown
    async def _decrease_countdown(pm) -> int | None:
        return await connection.scalar(
            payments_automation.update()
            .where(
                (payments_automation.c.payment_method_id == pm)
                & (payments_automation.c.inc_payments_countdown is not None)
            )
            .values(
                inc_payments_countdown=payments_automation.c.inc_payments_countdown - 1,
            )
            .returning(payments_automation.c.inc_payments_countdown)
        )

    assert _decrease_countdown(payment_method_id) == 4
    assert _decrease_countdown(payment_method_id) == 3
    assert _decrease_countdown(payment_method_id) == 2
    assert _decrease_countdown(payment_method_id) == 1
    assert _decrease_countdown(payment_method_id) == 0
    assert _decrease_countdown(payment_method_id) == -1

    # update auto-rechage
    async def _update_auto_recharge(pm, **updates) -> RowProxy:
        result = await connection.execute(
            payments_automation.update()
            .where(payments_automation.c.payment_method_id == pm)
            .values(**updates)
            .returning(sa.text("*"))
        )
        updated = await result.first()
        assert updated
        return updated

    await _update_auto_recharge(payment_method_id, inc_payments_countdown=None)
    assert _decrease_countdown(payment_method_id) is None
