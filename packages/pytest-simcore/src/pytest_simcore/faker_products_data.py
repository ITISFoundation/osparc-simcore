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
from pydantic import EmailStr, TypeAdapter

from .helpers.faker_factories import random_product

_MESSAGE = (
    "If set, it overrides the fake value of `{}` fixture."
    " Can be handy when interacting with external/real APIs"
)


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore")
    simcore_group.addoption(
        "--faker-support-email",
        action="store",
        type=str,
        default=None,
        help=_MESSAGE.format("support_email"),
    )
    simcore_group.addoption(
        "--faker-bcc-email",
        action="store",
        type=str,
        default=None,
        help=_MESSAGE.format("bcc_email"),
    )


@pytest.fixture
def product_name() -> ProductName:
    return ProductName("thetestproduct")


@pytest.fixture
def support_email(
    request: pytest.FixtureRequest, product_name: ProductName
) -> EmailStr:
    return TypeAdapter(EmailStr).validate_python(
        request.config.getoption("--faker-support-email", default=None)
        or f"support@{product_name}.info",
    )


@pytest.fixture
def bcc_email(request: pytest.FixtureRequest, product_name: ProductName) -> EmailStr:
    return TypeAdapter(EmailStr).validate_python(
        request.config.getoption("--faker-bcc-email", default=None)
        or f"finance@{product_name}-department.info",
    )


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
