# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from pathlib import Path
from typing import Any

import notifications_library
import pytest
from models_library.products import ProductName
from notifications_library._models import ProductData, UserData
from notifications_library.payments import PaymentData
from pydantic import EmailStr, parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.products import Vendor

pytest_plugins = [
    "pytest_simcore.environment_configs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.faker_payments_data",
    "pytest_simcore.faker_products_data",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.docker_compose",
    "pytest_simcore.postgres_service",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.tmp_path_extra",
]


@pytest.fixture(scope="session")
def package_dir() -> Path:
    pdir = Path(notifications_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir


def pytest_addoption(parser: pytest.Parser):
    group = parser.getgroup(
        "simcore",
    )
    group.addoption(
        "--external-user-email",
        action="store",
        type=str,
        default=None,
        help="Overrides `user_email` fixture",
    )
    group.addoption(
        "--external-support-email",
        action="store",
        type=str,
        default=None,
        help="Overrides `support_email` fixture",
    )


@pytest.fixture(scope="session")
def external_environment(external_environment: EnvVarsDict) -> EnvVarsDict:
    if external_environment:
        assert "PAYMENTS_GATEWAY_API_SECRET" in external_environment
        assert "PAYMENTS_GATEWAY_URL" in external_environment
    return external_environment


@pytest.fixture(scope="session")
def external_user_email(request: pytest.FixtureRequest) -> str | None:
    email_or_none = request.config.getoption("--external-user-email", default=None)
    return parse_obj_as(EmailStr, email_or_none) if email_or_none else None


@pytest.fixture
def user_email(user_email: EmailStr, external_user_email: EmailStr | None) -> EmailStr:
    """Overrides pytest_simcore.faker_users_data.user_email"""
    if external_user_email:
        print(
            f"📧 EXTERNAL `user_email` detected. Setting user_email={external_user_email}"
        )
        return external_user_email
    return user_email


@pytest.fixture(scope="session")
def external_bcc_email(request: pytest.FixtureRequest) -> str | None:
    email_or_none = request.config.getoption("--external-bcc-email", default=None)
    return parse_obj_as(EmailStr, email_or_none) if email_or_none else None


@pytest.fixture
def bcc_email(bbc_email: EmailStr, external_bcc_email: EmailStr | None) -> EmailStr:
    """Overrides pytest_simcore.faker_products_data.bcc_email"""
    if external_bcc_email:
        print(
            f"📧 EXTERNAL `bcc_email` detected. Setting bcc_email={external_user_email}"
        )
        return external_bcc_email
    return bcc_email


@pytest.fixture(scope="session")
def external_support_email(request: pytest.FixtureRequest) -> str | None:
    email_or_none = request.config.getoption("--external-support-email", default=None)
    return parse_obj_as(EmailStr, email_or_none) if email_or_none else None


@pytest.fixture
def support_email(
    support_email: EmailStr, external_support_email: EmailStr | None
) -> EmailStr:
    """Overrides pytest_simcore.faker_products_data.support_email"""
    if external_support_email:
        print(
            f"📧 EXTERNAL `support_email` detected. Setting support_email={external_support_email}"
        )
        return external_support_email
    return support_email


#
# mock data for templaes
#


@pytest.fixture
def product_data(
    product_name: ProductName,
    product: dict[str, Any],
) -> ProductData:
    vendor: Vendor = product["vendor"]

    return ProductData(  # type: ignore
        product_name=product_name,
        display_name=product["display_name"],
        vendor_display_inline=f"{vendor.get('name','')}, {vendor.get('address','')}",
        support_email=product["support_email"],
    )


@pytest.fixture
def user_data(
    user_email: EmailStr, user_first_name: str, user_last_name: str
) -> UserData:
    return UserData(
        first_name=user_first_name,
        last_name=user_last_name,
        email=user_email,
    )


@pytest.fixture
def payment_data(successful_transaction: dict[str, Any]) -> PaymentData:
    return PaymentData(
        price_dollars=successful_transaction["price_dollars"],
        osparc_credits=successful_transaction["osparc_credits"],
        invoice_url=successful_transaction["invoice_url"],
        invoice_pdf_url=successful_transaction["invoice_pdf_url"],
    )
