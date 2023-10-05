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
from simcore_postgres_database.models.payments_automation import payments_autorecharge
from simcore_postgres_database.models.payments_methods import (
    InitPromptAckFlowState,
    payments_methods,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert


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

UNSET = object()


async def _get_auto_recharge(connection, wallet_id) -> RowProxy | None:
    # has recharge trigger?
    stmt = (
        sa.select(
            payments_autorecharge.c.id.label("payments_autorecharge_id"),
            payments_methods.c.user_id,
            payments_autorecharge.c.wallet_id,
            payments_autorecharge.c.payment_method_id,
            payments_autorecharge.c.enabled,
            payments_autorecharge.c.min_balance_in_usd,
            payments_autorecharge.c.inc_payment_amount_in_usd,
            payments_autorecharge.c.inc_payments_countdown,
        )
        .select_from(
            payments_methods.join(
                payments_autorecharge,
                payments_methods.c.payment_method_id
                == payments_autorecharge.c.payment_method_id,
            )
        )
        .where(
            (payments_autorecharge.c.wallet_id == wallet_id)
            & (payments_methods.c.state == InitPromptAckFlowState.SUCCESS)
        )
    )
    result = await connection.execute(stmt)
    return await result.first()


async def _upsert_autorecharge(
    connection, wallet_id, payment_method, th=UNSET, ip=UNSET, cd=UNSET
) -> RowProxy:
    # using this primary payment-method, create an autorecharge

    values = {
        # ids
        "wallet_id": wallet_id,
        "payment_method_id": payment_method,
    }
    if th is not UNSET:
        values["min_balance_in_usd"] = th
    if ip is not UNSET:
        values["inc_payment_amount_in_usd"] = ip
    if cd is not UNSET:
        values["inc_payments_countdown"] = cd

    insert_stmt = pg_insert(payments_autorecharge).values(*values)
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=[
            payments_autorecharge.c.wallet_id,
            payments_autorecharge.c.payment_method_id,
        ],
        set_=values,
    ).returning(sa.literal_column("*"))

    row = await (await connection.execute(upsert_stmt)).first()
    assert row
    return row


async def _decrease_countdown(connection, wallet_id, payment_method) -> int | None:
    # updates payments countdown
    return await connection.scalar(
        payments_autorecharge.update()
        .where(
            (payments_autorecharge.c.wallet_id == wallet_id)
            & (payments_autorecharge.c.payment_method_id == payment_method)
            & (payments_autorecharge.c.inc_payments_countdown is not None)
        )
        .values(
            inc_payments_countdown=payments_autorecharge.c.inc_payments_countdown - 1,
        )
        .returning(payments_autorecharge.c.inc_payments_countdown)
    )


@pytest.mark.testit()
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
    wallet_id = payment_method_row.wallet_id

    # get
    auto_recharge = await _get_auto_recharge(connection, wallet_id)
    assert auto_recharge is None

    # new
    await _upsert_autorecharge(
        connection, wallet_id, payment_method_id, th=10, ip=100, cd=5
    )

    auto_recharge = await _get_auto_recharge(connection, wallet_id)
    assert auto_recharge is not None
    assert auto_recharge.payment_method_id == payment_method_id

    # countdown
    assert _decrease_countdown(connection, wallet_id, payment_method_id) == 4
    assert _decrease_countdown(connection, wallet_id, payment_method_id) == 3
    assert _decrease_countdown(connection, wallet_id, payment_method_id) == 2
    assert _decrease_countdown(connection, wallet_id, payment_method_id) == 1
    assert _decrease_countdown(connection, wallet_id, payment_method_id) == 0
    assert _decrease_countdown(connection, wallet_id, payment_method_id) == -1

    # deactivate countdown
    await _upsert_autorecharge(connection, wallet_id, payment_method_id, cd=None)
    assert _decrease_countdown(connection, wallet_id, payment_method_id) is None
    assert _decrease_countdown(connection, wallet_id, payment_method_id) is None
