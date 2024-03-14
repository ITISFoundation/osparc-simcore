# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
"""
    Fixtures to produce fake data for a product:
        - it is self-consistent
        - granular customization by overriding fixtures
"""

from typing import Any

import pytest
from faker import Faker
from models_library.products import ProductName, StripePriceID, StripeTaxRateID
from pydantic import EmailStr

from .helpers.rawdata_fakers import random_product


@pytest.fixture
def product_name() -> ProductName:
    return ProductName("the_test_product")


@pytest.fixture
def support_email(product_name: ProductName) -> EmailStr:
    return EmailStr(f"support@{product_name}.info")


@pytest.fixture
def product(
    faker: Faker, product_name: ProductName, support_email: EmailStr
) -> dict[str, Any]:
    return random_product(name=product_name, support_email=support_email, fake=faker)


@pytest.fixture
def product_price_stripe_price_id(faker: Faker) -> StripePriceID:
    return StripePriceID(faker.word())


@pytest.fixture
def product_price_stripe_tax_rate_id(faker: Faker) -> StripeTaxRateID:
    return StripeTaxRateID(faker.word())
