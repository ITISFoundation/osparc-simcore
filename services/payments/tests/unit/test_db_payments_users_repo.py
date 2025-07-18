# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from models_library.groups import GroupID
from models_library.users import UserID
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from pytest_simcore.helpers.postgres_users import (
    insert_and_get_user_and_secrets_lifespan,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.payments_transactions import payments_transactions
from simcore_postgres_database.models.products import products
from simcore_service_payments.db.payment_users_repo import PaymentsUsersRepo
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
    async with insert_and_get_user_and_secrets_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        get_engine(app), **user
    ) as user_row:
        yield user_row


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
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        get_engine(app),
        table=products,
        values=product,
        pk_col=products.c.name,
        pk_value=product["name"],
    ) as row:
        yield row


@pytest.fixture
async def successful_transaction(
    app: FastAPI, successful_transaction: dict[str, Any]
) -> AsyncIterator[dict[str, Any]]:
    """
    injects transaction in db
    """
    async with insert_and_get_row_lifespan(  # pylint:disable=contextmanager-generator-missing-cleanup
        get_engine(app),
        table=payments_transactions,
        values=successful_transaction,
        pk_col=payments_transactions.c.payment_id,
        pk_value=successful_transaction["payment_id"],
    ) as row:
        yield row


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
