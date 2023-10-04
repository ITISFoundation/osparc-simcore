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
