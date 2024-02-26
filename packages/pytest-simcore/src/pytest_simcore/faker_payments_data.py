# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""

Needs including pytest_plugins = [
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_users_data",
]


"""

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from faker import Faker
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, parse_obj_as
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

from .helpers.rawdata_fakers import random_payment_transaction


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return parse_obj_as(WalletID, faker.pyint())


@pytest.fixture
def wallet_name(faker: Faker) -> IDStr:
    return parse_obj_as(IDStr, f"wallet-{faker.word()}")


@pytest.fixture
def successful_transaction(
    faker: Faker,
    wallet_id: WalletID,
    user_email: EmailStr,
    user_id: UserID,
    product_name: ProductName,
) -> dict[str, Any]:

    initiated_at = datetime.now(tz=timezone.utc)
    return random_payment_transaction(
        payment_id=f"pt_{faker.pyint()}",
        price_dollars=faker.pydecimal(positive=True, right_digits=2, left_digits=4),
        state=PaymentTransactionState.SUCCESS,
        initiated_at=initiated_at,
        completed_at=initiated_at + timedelta(seconds=10),
        osparc_credits=faker.pydecimal(positive=True, right_digits=2, left_digits=4),
        product_name=product_name,
        user_id=user_id,
        user_email=user_email,
        wallet_id=wallet_id,
        comment=f"fake fixture in {__name__}.successful_transaction",
        invoice_url=faker.image_url(),
    )
