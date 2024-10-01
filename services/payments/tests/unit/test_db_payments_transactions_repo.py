# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)
from simcore_service_payments.models.db import (
    PaymentsTransactionsDB,
    PaymentTransactionState,
)

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


async def test_one_time_payment_annotations_workflow(app: FastAPI):

    fake = PaymentsTransactionsDB(
        **PaymentsTransactionsDB.model_config["json_schema_extra"]["examples"][1]
    )

    repo = PaymentsTransactionsRepo(app.state.engine)

    # annotate init
    payment_id = await repo.insert_init_payment_transaction(
        payment_id=fake.payment_id,
        price_dollars=fake.price_dollars,
        product_name=fake.product_name,
        user_id=fake.user_id,
        user_email=fake.user_email,
        wallet_id=fake.wallet_id,
        comment=fake.comment,
        osparc_credits=fake.osparc_credits,
        initiated_at=fake.initiated_at,
    )

    # annotate ack
    assert fake.invoice_url is not None
    transaction_acked = await repo.update_ack_payment_transaction(
        payment_id=fake.payment_id,
        completion_state=PaymentTransactionState.SUCCESS,
        invoice_url=fake.invoice_url,
        invoice_pdf_url=fake.invoice_pdf_url,
        stripe_invoice_id=fake.stripe_invoice_id,
        state_message="DONE",
    )

    assert transaction_acked.payment_id == payment_id

    # list
    total_number_of_items, user_payments = await repo.list_user_payment_transactions(
        user_id=fake.user_id, product_name=fake.product_name
    )
    assert total_number_of_items == 1
    assert len(user_payments) == total_number_of_items
    assert user_payments[0] == transaction_acked
