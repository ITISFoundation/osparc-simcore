# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

from models_library.products import ProductName
from models_library.users import GroupID, UserID
from notifications_library._db import TemplatesRepo
from notifications_library._payments_db import PaymentsDataRepo
from sqlalchemy.ext.asyncio.engine import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_templates_repo(
    sqlalchemy_async_engine: AsyncEngine,
    user_id: UserID,
    user_primary_group_id: GroupID,
):
    repo = TemplatesRepo(sqlalchemy_async_engine)
    assert await repo.get_primary_group_id(user_id) == user_primary_group_id


async def test_get_on_payed_data(
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


async def test_get_email_templates(
    sqlalchemy_async_engine: AsyncEngine,
    email_templates: dict[str, Any],
    product_name: ProductName,
):
    repo = TemplatesRepo(sqlalchemy_async_engine)

    templates = await repo.get_email_templates(
        names=set(email_templates.keys()), product=product_name
    )

    assert {t.name: t.content for t in templates} == {
        key: value["content"] for key, value in email_templates.items()
    }
