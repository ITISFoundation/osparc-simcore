# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.models.db import InitPromptAckFlowState, PaymentsMethodsDB

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


async def test_create_payments_method_annotations_workflow(app: FastAPI):

    fake = PaymentsMethodsDB(
        **PaymentsMethodsDB.model_config["json_schema_extra"]["examples"][1]
    )

    repo = PaymentsMethodsRepo(app.state.engine)

    # annotate init
    payment_method_id = await repo.insert_init_payment_method(
        fake.payment_method_id,
        user_id=fake.user_id,
        wallet_id=fake.wallet_id,
        initiated_at=fake.initiated_at,
    )

    assert payment_method_id == fake.payment_method_id

    # annotate ack
    acked = await repo.update_ack_payment_method(
        fake.payment_method_id,
        completion_state=InitPromptAckFlowState.SUCCESS,
        state_message="DONE",
    )

    # list
    listed = await repo.list_user_payment_methods(
        user_id=fake.user_id,
        wallet_id=fake.wallet_id,
    )
    assert len(listed) == 1
    assert listed[0] == acked

    # get
    got = await repo.get_payment_method(
        payment_method_id,
        user_id=fake.user_id,
        wallet_id=fake.wallet_id,
    )
    assert got == acked

    # delete
    deleted = await repo.delete_payment_method(
        payment_method_id,
        user_id=fake.user_id,
        wallet_id=fake.wallet_id,
    )
    assert deleted == got

    listed = await repo.list_user_payment_methods(
        user_id=fake.user_id,
        wallet_id=fake.wallet_id,
    )
    assert not listed
