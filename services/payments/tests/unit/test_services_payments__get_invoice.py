# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.payments import StripeInvoiceID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import HttpUrl
from pytest_simcore.helpers.faker_factories import random_payment_transaction
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_products import insert_and_get_product_lifespan
from pytest_simcore.helpers.postgres_users import (
    insert_and_get_user_and_secrets_lifespan,
)
from pytest_simcore.helpers.postgres_wallets import insert_and_get_wallet_lifespan
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
    payments_transactions,
)
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)
from simcore_service_payments.services import payments
from simcore_service_payments.services.stripe import StripeApi
from sqlalchemy.ext.asyncio import AsyncEngine

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
    with_disabled_rabbitmq_and_rpc: None,
    postgres_env_vars_dict: EnvVarsDict,
    wait_for_postgres_ready_and_db_migrated: None,
):
    # set environs
    monkeypatch.delenv("PAYMENTS_RABBITMQ", raising=False)
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **postgres_env_vars_dict,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


@pytest.fixture()
async def populate_payment_transaction_db(
    sqlalchemy_async_engine: AsyncEngine,
    wallet_id: int,
    user_id: UserID,
    product_name: ProductName,
    invoice_url: HttpUrl,
    stripe_invoice_id: StripeInvoiceID | None,
) -> AsyncIterator[PaymentID]:
    async with (
        insert_and_get_user_and_secrets_lifespan(sqlalchemy_async_engine, id=user_id) as user_row,
        insert_and_get_product_lifespan(sqlalchemy_async_engine, name=product_name),
        insert_and_get_wallet_lifespan(
            sqlalchemy_async_engine,
            product_name=product_name,
            user_group_id=user_row["primary_gid"],
            wallet_id=wallet_id,
        ),
    ):
        async with sqlalchemy_async_engine.begin() as con:
            result = await con.execute(
                payments_transactions.insert()
                .values(
                    **random_payment_transaction(
                        price_dollars=Decimal(9500),
                        wallet_id=wallet_id,
                        user_id=user_id,
                        state=PaymentTransactionState.SUCCESS,
                        completed_at=datetime.now(tz=UTC),
                        initiated_at=datetime.now(tz=UTC) - timedelta(seconds=10),
                        invoice_url=invoice_url,
                        stripe_invoice_id=stripe_invoice_id,
                    )
                )
                .returning(payments_transactions.c.payment_id)
            )
            row = result.first()

        yield cast(PaymentID, row[0])

        async with sqlalchemy_async_engine.begin() as con:
            await con.execute(payments_transactions.delete())


@pytest.mark.parametrize(
    "invoice_url,stripe_invoice_id",
    [
        ("https://my-fake-pdf-link.com", None),
        ("https://my-fake-pdf-link.com", "in_12345"),
    ],
    indirect=True,
)
async def test_get_payment_invoice_url(
    app: FastAPI,
    populate_payment_transaction_db: PaymentID,
    mock_stripe_or_none: MockRouter | None,
    wallet_id: WalletID,
    user_id: UserID,
):
    invoice_url = await payments.get_payment_invoice_url(
        repo=PaymentsTransactionsRepo(db_engine=app.state.engine),
        stripe_api=StripeApi.get_from_app_state(app),
        user_id=user_id,
        wallet_id=wallet_id,
        payment_id=populate_payment_transaction_db,
    )
    assert invoice_url
    assert isinstance(invoice_url, HttpUrl)
