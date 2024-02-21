# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import importlib.resources
from collections.abc import AsyncIterator
from typing import Any

import notifications_library
import pytest
import sqlalchemy as sa
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from notifications_library._db import TemplatesRepo
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from sqlalchemy.ext.asyncio.engine import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def _insert_and_get_row(
    conn, table: sa.Table, values: dict[str, Any], pk_col: sa.Column, pk_value: Any
):
    result = await conn.execute(table.insert().values(**values).returning(pk_col))
    row = result.first()
    assert row[pk_col] == pk_value

    result = await conn.execute(sa.select(table).where(pk_col == pk_value))
    return result.first()


async def _delete_row(conn, table, pk_col: sa.Column, pk_value: Any):
    await conn.execute(table.delete().where(pk_col == pk_value))


@pytest.fixture
async def user(
    sqlalchemy_async_engine: AsyncEngine,
    user: dict[str, Any],
    user_id: UserID,
) -> AsyncIterator[dict[str, Any]]:
    """Overrides pytest_simcore.faker_users_data.user
    and injects a user in db
    """
    assert user_id == user["id"]
    pk_args = users.c.id, user["id"]

    # NOTE: creation of primary group and setting `groupid`` is automatically triggered after creation of user by postgres
    async with sqlalchemy_async_engine.begin() as conn:
        row = await _insert_and_get_row(conn, users, user, *pk_args)

    yield dict(row)

    async with sqlalchemy_async_engine.begin() as conn:
        await _delete_row(conn, users, *pk_args)


@pytest.fixture
def user_primary_group_id(user: dict[str, Any]) -> GroupID:
    # Overrides `user_primary_group_id` since new user triggers an automatic creation of a primary group
    return user["primary_gid"]


@pytest.fixture
async def product(
    sqlalchemy_async_engine: AsyncEngine, product: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Overrides pytest_simcore.faker_products_data.product
    and injects product in db
    """
    # NOTE: this fixture ignores products' group-id but it is fine for this test context
    assert product["group_id"] is None
    pk_args = products.c.name, product["name"]

    async with sqlalchemy_async_engine.begin() as conn:
        row = await _insert_and_get_row(conn, products, product, *pk_args)

    yield dict(row)

    async with sqlalchemy_async_engine.begin() as conn:
        await _delete_row(conn, products, *pk_args)


@pytest.fixture
async def successful_transaction(
    sqlalchemy_async_engine: AsyncEngine, successful_transaction: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Overrides pytest_simcore.faker_payments_data.successful_transaction
    and injects transaction in db
    """
    pk_args = payments_transactions.c.payment_id, successful_transaction["payment_id"]

    async with sqlalchemy_async_engine.begin() as conn:
        row = await _insert_and_get_row(
            conn, payments_transactions, successful_transaction, *pk_args
        )

    yield dict(row)

    async with sqlalchemy_async_engine.begin() as conn:
        await _delete_row(conn, payments_transactions, *pk_args)


async def test_templates_repo(
    sqlalchemy_async_engine: AsyncEngine,
    user_id: UserID,
    user_primary_group_id: GroupID,
):
    repo = TemplatesRepo(sqlalchemy_async_engine)
    assert await repo.get_primary_group_id(user_id) == user_primary_group_id


async def test_get_notification_data(
    sqlalchemy_async_engine: AsyncEngine,
    user: dict[str, Any],
    product: dict[str, Any],
    successful_transaction: dict[str, Any],
):
    repo = TemplatesRepo(sqlalchemy_async_engine)

    # check once
    data = await repo.get_notify_payments_data(
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


@pytest.fixture
async def email_templates(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[dict[str, Any]]:
    all_templates = {"other.html": "Fake template"}

    templates_path = importlib.resources.files(notifications_library).joinpath(
        "templates"
    )
    for path in templates_path.iterdir():
        all_templates[path.name] = path.read_text()

    async with sqlalchemy_async_engine.begin() as conn:
        pk_to_row = {
            pk_value: await _insert_and_get_row(
                conn,
                jinja2_templates,
                {"name": pk_value, "content": content},
                jinja2_templates.c.name,
                pk_value,
            )
            for pk_value, content in all_templates.items()
        }

    yield pk_to_row

    async with sqlalchemy_async_engine.begin() as conn:
        for pk_value in pk_to_row:
            await _delete_row(conn, jinja2_templates, jinja2_templates.c.name, pk_value)


async def test_get_payments_templates(
    sqlalchemy_async_engine: AsyncEngine,
    email_templates: dict[str, Any],
    product_name: ProductName,
):
    repo = TemplatesRepo(sqlalchemy_async_engine)

    templates = await repo.get_email_templates(
        names=set(email_templates.keys()), product=product_name
    )

    assert templates == {
        key: value["content"] for key, value in email_templates.items()
    }
