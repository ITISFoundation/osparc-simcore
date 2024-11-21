# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator
from typing import Any

import pytest
import sqlalchemy as sa
from models_library.basic_types import IDStr
from models_library.products import ProductName
from models_library.users import GroupID, UserID
from notifications_library._templates import get_default_named_templates
from pydantic import validate_call
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.products_to_templates import products_to_templates
from simcore_postgres_database.models.users import users
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio.engine import AsyncEngine


async def _insert_and_get_row(
    conn, table: sa.Table, values: dict[str, Any], pk_col: sa.Column, pk_value: Any
) -> Row:
    result = await conn.execute(table.insert().values(**values).returning(pk_col))
    row = result.first()
    assert getattr(row, pk_col.name) == pk_value

    result = await conn.execute(sa.select(table).where(pk_col == pk_value))
    return result.first()


async def _delete_row(conn, table, pk_col: sa.Column, pk_value: Any) -> None:
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
        row: Row = await _insert_and_get_row(conn, users, user, *pk_args)

    yield row._asdict()

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

    # NOTE: osparc product is already in db. This is another product
    assert product["name"] != "osparc"

    pk_args = products.c.name, product["name"]

    async with sqlalchemy_async_engine.begin() as conn:
        row: Row = await _insert_and_get_row(conn, products, product, *pk_args)

    yield row._asdict()

    async with sqlalchemy_async_engine.begin() as conn:
        await _delete_row(conn, products, *pk_args)


@pytest.fixture
async def products_names(
    sqlalchemy_async_engine: AsyncEngine, product: dict[str, Any]
) -> list[ProductName]:
    # overrides
    async with sqlalchemy_async_engine.begin() as conn:
        result = await conn.execute(sa.select(products.c.name))
        all_product_names = [row.name for row in result.fetchall()]
        assert product["name"] in all_product_names
        return all_product_names


@pytest.fixture
async def successful_transaction(
    sqlalchemy_async_engine: AsyncEngine, successful_transaction: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """Overrides pytest_simcore.faker_payments_data.successful_transaction
    and injects transaction in db
    """
    pk_args = payments_transactions.c.payment_id, successful_transaction["payment_id"]

    async with sqlalchemy_async_engine.begin() as conn:
        row: Row = await _insert_and_get_row(
            conn, payments_transactions, successful_transaction, *pk_args
        )

    yield row._asdict()

    async with sqlalchemy_async_engine.begin() as conn:
        await _delete_row(conn, payments_transactions, *pk_args)


@pytest.fixture
def email_template_mark() -> str:
    return f"Added by {__name__}:email_templates fixture"


@pytest.fixture
async def email_templates(
    sqlalchemy_async_engine: AsyncEngine, email_template_mark: str
) -> AsyncIterator[dict[str, Any]]:
    all_templates = {"other.html": f"Fake template {email_template_mark}"}

    # only subjects are overriden in db
    subject_templates = get_default_named_templates(media="email", part="subject")
    for name, path in subject_templates.items():
        assert "subject" in name
        all_templates[name] = f"{email_template_mark} {path.read_text()}"

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


@pytest.fixture
def set_template_to_product(
    sqlalchemy_async_engine: AsyncEngine, product: dict[str, Any]
):
    # NOTE: needs all fixture products in db
    @validate_call
    async def _(template_name: IDStr, product_name: ProductName) -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                products_to_templates.insert().values(
                    product_name=product_name, template_name=template_name
                )
            )

    return _


@pytest.fixture
def unset_template_to_product(sqlalchemy_async_engine: AsyncEngine):
    @validate_call
    async def _(template_name: IDStr, product_name: ProductName) -> None:
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                products_to_templates.delete().where(
                    (products_to_templates.c.product_name == product_name)
                    & (products_to_templates.c.template_name == template_name)
                )
            )

    return _
