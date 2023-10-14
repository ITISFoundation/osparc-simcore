# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.rawdata_fakers import random_payment_transaction
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)
from simcore_service_payments.models.db import (
    PaymentsTransactionsDB,
    PaymentTransactionState,
)

pytest_simcore_core_services_selection = [
    "postgres",
    "rabbit",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    postgres_env_vars_dict: EnvVarsDict,
    postgres_ready_and_db_migrated: None,
    disable_rabbitmq_and_rpc_setup: Callable,
):
    disable_rabbitmq_and_rpc_setup()

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
    # TODO: add hypothesis here!
    expected = PaymentsTransactionsDB.parse_obj(random_payment_transaction())

    repo = PaymentsTransactionsRepo(app.state.engine)

    # annotate init
    payment_id = await repo.insert_init_payment_transaction(
        payment_id=expected.payment_id,
        price_dollars=expected.price_dollars,
        product_name=expected.product_name,
        user_id=expected.user_id,
        user_email=expected.user_email,
        wallet_id=expected.wallet_id,
        comment=expected.comment,
        osparc_credits=expected.osparc_credits,
        initiated_at=expected.initiated_at,
    )

    # annotate ack
    transaction_acked = await repo.update_ack_payment_transaction(
        payment_id=expected.payment_id,
        completion_state=PaymentTransactionState.SUCCESS,
        invoice_url=expected.invoice_url,
        state_message="DONE",
    )

    # list
    user_payments = await repo.list_user_payment_transactions(user_id=expected.user_id)
    assert user_payments
    assert len(user_payments) == 1
    assert user_payments[0] == transaction_acked


# errors:
# -  annotate ack -> error
#
# annotate cancel
#
