# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
import os
from typing import Any

import pytest
from faker import Faker
from models_library.notifications import (
    CompanyLink,
    Product,
    ProductFooterData,
    ProductUI,
    Sharer,
    SocialLink,
    UserData,
)
from models_library.products import ProductName
from pydantic import EmailStr
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.products import Vendor
from simcore_service_notifications.models.payments import PaymentData
from simcore_service_notifications.models.smtp import SMTPSettings

pytest_plugins = [
    "pytest_simcore.faker_payments_data",
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_users_data",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    env_devel_dict: EnvVarsDict,
    external_envfile_dict: EnvVarsDict,
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
            **external_envfile_dict,
        },
    )


@pytest.fixture
def with_smtp_extra_headers(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    headers = {"x-ses-tenant": "test-tenant"}
    setenvs_from_dict(monkeypatch, {"SMTP_EXTRA_HEADERS": json.dumps(headers)})
    return headers


@pytest.fixture
def smtp_settings(
    app_environment: EnvVarsDict,
    with_smtp_extra_headers: dict[str, str],
) -> SMTPSettings:
    return SMTPSettings(
        host=os.environ.get("SMTP_HOST", "localhost"),
        port=int(os.environ.get("SMTP_PORT", "1025")),
        protocol=os.environ.get("SMTP_PROTOCOL", "UNENCRYPTED"),
        username=os.environ.get("SMTP_USERNAME"),
        password=os.environ.get("SMTP_PASSWORD"),
        extra_headers=json.loads(os.environ.get("SMTP_EXTRA_HEADERS", "{}")),
        domain=os.environ.get("SMTP_DOMAIN", "osparc.io"),
        local_parts=json.loads(os.environ.get("SMTP_LOCAL_PARTS", '{"SUPPORT": "support", "NO_REPLY": "no-reply"}')),
    )


#
# mock data for templates
#


@pytest.fixture
def product_data(
    product_name: ProductName,
    product: dict[str, Any],
) -> Product:
    vendor: Vendor = product["vendor"]

    vendor_ui = vendor.get("ui", {})

    product_ui = ProductUI(
        logo_url=vendor_ui.get("logo_url"),
        strong_color=vendor_ui.get("strong_color"),
    )

    footer_data = ProductFooterData(
        social_links=[
            SocialLink(name=link_name, url=link_url) for link_name, link_url in vendor.get("footer_social_links", [])
        ],
        company_name=vendor.get("company_name", ""),
        company_address=vendor.get("company_address", ""),
        company_links=[
            CompanyLink(name=link_name, url=link_url) for link_name, link_url in vendor.get("company_links", [])
        ],
    )

    return Product(
        product_name=product_name,
        display_name=product["display_name"],
        vendor_display_inline=f"{vendor.get('name', '')}, {vendor.get('address', '')}",
        support_email=product["support_email"],
        homepage_url=vendor.get("url"),
        ui=product_ui,
        footer=footer_data,
    )


@pytest.fixture
def user_data(user_name: str, user_email: EmailStr, user_first_name: str, user_last_name: str) -> UserData:
    return UserData(
        user_name=user_name,
        first_name=user_first_name,
        last_name=user_last_name,
        email=user_email,
    )


@pytest.fixture
def sharer_data(user_name: str, faker: Faker) -> Sharer:
    return Sharer(
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
