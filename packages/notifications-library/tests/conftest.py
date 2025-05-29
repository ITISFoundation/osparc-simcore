# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pathlib import Path
from typing import Any

import notifications_library
import pytest
from faker import Faker
from models_library.products import ProductName
from notifications_library._models import (
    ProductData,
    ProductUIData,
    SharerData,
    UserData,
)
from notifications_library.payments import PaymentData
from pydantic import EmailStr
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.products import Vendor

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_payments_data",
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.postgres_service",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(notifications_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def external_envfile_dict(external_envfile_dict: EnvVarsDict) -> EnvVarsDict:
    if external_envfile_dict:
        assert "PAYMENTS_GATEWAY_API_SECRET" in external_envfile_dict
        assert "PAYMENTS_GATEWAY_URL" in external_envfile_dict
    return external_envfile_dict


#
# mock data for templates
#


@pytest.fixture
def product_data(
    product_name: ProductName,
    product: dict[str, Any],
) -> ProductData:
    vendor: Vendor = product["vendor"]

    vendor_ui = vendor.get("ui", {})

    product_ui = ProductUIData(
        logo_url=vendor_ui.get("logo_url"),
        strong_color=vendor_ui.get("strong_color"),
        project_alias=vendor_ui["project_alias"],
    )

    return ProductData(  # type: ignore
        product_name=product_name,
        display_name=product["display_name"],
        vendor_display_inline=f"{vendor.get('name','')}, {vendor.get('address','')}",
        support_email=product["support_email"],
        homepage_url=vendor.get("url"),
        ui=product_ui,
    )


@pytest.fixture
def user_data(
    user_name: str, user_email: EmailStr, user_first_name: str, user_last_name: str
) -> UserData:
    return UserData(
        user_name=user_name,
        first_name=user_first_name,
        last_name=user_last_name,
        email=user_email,
    )


@pytest.fixture
def sharer_data(user_name: str, faker: Faker) -> SharerData:
    return SharerData(
        user_name=user_name,
        message=faker.random_element(elements=(faker.sentence(), "")),
    )


@pytest.fixture
def payment_data(successful_transaction: dict[str, Any]) -> PaymentData:
    return PaymentData(
        price_dollars=successful_transaction["price_dollars"],
        osparc_credits=successful_transaction["osparc_credits"],
        invoice_url=successful_transaction["invoice_url"],
        invoice_pdf_url=successful_transaction["invoice_pdf_url"],
    )
