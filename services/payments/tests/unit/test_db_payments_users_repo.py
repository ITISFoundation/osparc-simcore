# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.users import GroupID, UserID
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_postgres_database.models.jinja2_templates import jinja2_templates
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.users import users
from simcore_service_payments.db.payment_users_repo import PaymentsUsersRepo
from simcore_service_payments.services.notifier_email import (
    _PRODUCT_NOTIFICATIONS_TEMPLATES,
)
from simcore_service_payments.services.postgres import get_engine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    postgres_env_vars_dict: EnvVarsDict,
    with_disabled_rabbitmq_and_rpc: None,
    wait_for_postgres_ready_and_db_migrated: None,
):
    # set environs
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


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
    app: FastAPI,
    user: dict[str, Any],
    user_id: UserID,
) -> AsyncIterator[dict[str, Any]]:
    """
    injects a user in db
    """
    assert user_id == user["id"]
    pk_args = users.c.id, user["id"]

    # NOTE: creation of primary group and setting `groupid`` is automatically triggered after creation of user by postgres
    async with get_engine(app).begin() as conn:
        row = await _insert_and_get_row(conn, users, user, *pk_args)

    yield dict(row)

    async with get_engine(app).begin() as conn:
        await _delete_row(conn, users, *pk_args)


@pytest.fixture
def user_primary_group_id(user: dict[str, Any]) -> GroupID:
    # Overrides `user_primary_group_id` since new user triggers an automatic creation of a primary group
    return user["primary_gid"]


@pytest.fixture
async def product(
    app: FastAPI, product: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """
    injects product in db
    """
    # NOTE: this fixture ignores products' group-id but it is fine for this test context
    assert product["group_id"] is None
    pk_args = products.c.name, product["name"]

    async with get_engine(app).begin() as conn:
        row = await _insert_and_get_row(conn, products, product, *pk_args)

    yield dict(row)

    async with get_engine(app).begin() as conn:
        await _delete_row(conn, products, *pk_args)


@pytest.fixture
async def successful_transaction(
    app: FastAPI, successful_transaction: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """
    injects transaction in db
    """
    pk_args = payments_transactions.c.payment_id, successful_transaction["payment_id"]

    async with get_engine(app).begin() as conn:
        row = await _insert_and_get_row(
            conn, payments_transactions, successful_transaction, *pk_args
        )

    yield dict(row)

    async with get_engine(app).begin() as conn:
        await _delete_row(conn, payments_transactions, *pk_args)


async def test_payments_user_repo(
    app: FastAPI, user_id: UserID, user_primary_group_id: GroupID
):
    repo = PaymentsUsersRepo(get_engine(app))
    assert await repo.get_primary_group_id(user_id) == user_primary_group_id


async def test_get_notification_data(
    app: FastAPI,
    user: dict[str, Any],
    product: dict[str, Any],
    successful_transaction: dict[str, Any],
):
    repo = PaymentsUsersRepo(get_engine(app))

    # check once
    data = await repo.get_notification_data(
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
async def email_templates(app: FastAPI) -> AsyncIterator[dict[str, Any]]:
    all_templates = {**_PRODUCT_NOTIFICATIONS_TEMPLATES, "other.html": "Fake template"}

    async with get_engine(app).begin() as conn:
        pk_to_row = {
            pk_value: await _insert_and_get_row(
                conn,
                jinja2_templates,
                {"content": content},
                jinja2_templates.c.name,
                pk_value,
            )
            for pk_value, content in all_templates.items()
        }

    yield pk_to_row

    async with get_engine(app).begin() as conn:
        for pk_value in pk_to_row:
            await _delete_row(
                conn, payments_transactions, jinja2_templates.c.name, pk_value
            )


async def test_get_payments_templates(
    app: FastAPI,
    email_templates: dict[str, Any],
):
    repo = PaymentsUsersRepo(get_engine(app))

    templates = await repo.get_email_templates(
        names=set(_PRODUCT_NOTIFICATIONS_TEMPLATES.keys())
    )

    assert templates == _PRODUCT_NOTIFICATIONS_TEMPLATES

    # TODO: see expore dependencies and pull all
