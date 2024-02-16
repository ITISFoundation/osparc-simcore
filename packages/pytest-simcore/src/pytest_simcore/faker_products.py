# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from faker import Faker
from models_library.products import ProductName
from pydantic import EmailStr
from pytest_simcore.helpers.rawdata_fakers import random_product


@pytest.fixture
def product_name() -> ProductName:
    return ProductName("osparc")


@pytest.fixture
def support_email(product_name: ProductName) -> EmailStr:
    return EmailStr(f"support@{product_name}.io")


@pytest.fixture
def product(
    faker: Faker, product_name: ProductName, support_email: EmailStr
) -> dict[str, Any]:
    return random_product(name=product_name, support_email=support_email, fake=faker)
