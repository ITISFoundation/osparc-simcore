# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import cast

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.payments import StripeInvoiceID
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import HttpUrl
from pytest_simcore.helpers.faker_factories import random_payment_transaction
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
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
def populate_payment_transaction_db(
    postgres_db: sa.engine.Engine,
    wallet_id: int,
    user_id: UserID,
    invoice_url: HttpUrl,
    stripe_invoice_id: StripeInvoiceID | None,
) -> Iterator[PaymentID]:
    with postgres_db.connect() as con:
        result = con.execute(
            payments_transactions.insert()
            .values(
                **random_payment_transaction(
                    price_dollars=Decimal(9500),
                    wallet_id=wallet_id,
                    user_id=user_id,
                    state=PaymentTransactionState.SUCCESS,
                    completed_at=datetime.now(tz=timezone.utc),
                    initiated_at=datetime.now(tz=timezone.utc) - timedelta(seconds=10),
                    invoice_url=invoice_url,
                    stripe_invoice_id=stripe_invoice_id,
                )
            )
            .returning(payments_transactions.c.payment_id)
        )
        row = result.first()

        yield cast(PaymentID, row[0])

        con.execute(payments_transactions.delete())


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
        #
        user_id=user_id,
        wallet_id=wallet_id,
        payment_id=populate_payment_transaction_db,
    )
    assert invoice_url
    assert isinstance(invoice_url, HttpUrl)
