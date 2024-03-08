# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable, Coroutine
from typing import Any

from models_library.products import ProductName
from models_library.users import UserID
from notifications_library._db import TemplatesRepo, UsersRepo
from notifications_library._models import UserData
from notifications_library._payments_db import PaymentsDataRepo
from sqlalchemy.ext.asyncio.engine import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_user_data_repo(
    sqlalchemy_async_engine: AsyncEngine,
    user: dict,
    user_id: UserID,
    user_data: UserData,
):
    assert user["id"] == user_id

    repo = UsersRepo(sqlalchemy_async_engine)
    got = await repo.get_user_data(user_id)
    assert UserData(*got) == user_data


async def test_payments_data_repo(
    sqlalchemy_async_engine: AsyncEngine,
    user: dict[str, Any],
    product: dict[str, Any],
    successful_transaction: dict[str, Any],
):
    repo = PaymentsDataRepo(sqlalchemy_async_engine)

    # check once
    data = await repo.get_on_payed_data(
        user_id=user["id"], payment_id=successful_transaction["payment_id"]
    )

    assert data.payment_id == successful_transaction["payment_id"]
    assert data.first_name == user["first_name"]
    assert data.last_name == user["last_name"]
    assert data.email == user["email"]
    assert data.product_name == product["name"]
    assert data.display_name == product["display_name"]
    assert data.vendor == product["vendor"]
    assert data.support_email == product["support_email"]


async def test_templates_repo(
    sqlalchemy_async_engine: AsyncEngine,
    email_templates: dict[str, Any],
    email_template_mark: dict,
    product_name: ProductName,
    set_template_to_product: Callable[[str, ProductName], Coroutine],
):
    repo = TemplatesRepo(sqlalchemy_async_engine)

    one_template_name = next(_ for _ in email_templates if "email" in _)
    await set_template_to_product(one_template_name, product_name)

    async for template in repo.iter_email_templates(product_name):
        assert template.name in email_templates
        assert email_template_mark in template.content
        assert template.name == one_template_name
