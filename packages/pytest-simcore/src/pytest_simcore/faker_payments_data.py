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
from models_library.payments import StripeInvoiceID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, HttpUrl, TypeAdapter
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

from .helpers.faker_factories import random_payment_transaction


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return TypeAdapter(WalletID).validate_python(faker.pyint())


@pytest.fixture
def wallet_name(faker: Faker) -> IDStr:
    return TypeAdapter(IDStr).validate_python(f"wallet-{faker.word()}")


@pytest.fixture
def invoice_url(faker: Faker) -> str:
    return faker.image_url()


@pytest.fixture
def invoice_pdf_url(faker: Faker) -> str:
    return faker.image_url()


@pytest.fixture
def stripe_invoice_id(faker: Faker) -> StripeInvoiceID:
    return TypeAdapter(StripeInvoiceID).validate_python(f"in_{faker.word()}")


@pytest.fixture
def successful_transaction(
    faker: Faker,
    wallet_id: WalletID,
    user_email: EmailStr,
    user_id: UserID,
    product_name: ProductName,
    invoice_url: HttpUrl,
    invoice_pdf_url: HttpUrl,
    stripe_invoice_id: StripeInvoiceID,
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
        invoice_url=invoice_url,
        invoice_pdf_url=invoice_pdf_url,
        stripe_invoice_id=stripe_invoice_id,
    )
