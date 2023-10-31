# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.wallets import PaymentMethodInitiated
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient
from simcore_service_payments.api.rpc.routes import PAYMENTS_RPC_NAMESPACE
from simcore_service_payments.db.payments_methods_repo import PaymentsMethodsRepo
from simcore_service_payments.models.db import InitPromptAckFlowState

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
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
    postgres_env_vars_dict: EnvVarsDict,
    wait_for_postgres_ready_and_db_migrated: None,
    external_environment: EnvVarsDict,
):
    # set environs
    monkeypatch.delenv("PAYMENTS_RABBITMQ", raising=False)
    monkeypatch.delenv("PAYMENTS_POSTGRES", raising=False)

    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            **rabbit_env_vars_dict,
            **postgres_env_vars_dict,
            **external_environment,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


async def test_webserver_init_and_cancel_payment_method_workflow(
    is_pdb_enabled: bool,
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mock_payments_gateway_service_or_none: MockRouter | None,
    faker: Faker,
    payments_clean_db: None,
):
    assert app
    user_id = faker.pyint()
    wallet_id = faker.pyint()

    rpc_client = await rabbitmq_rpc_client("web-server-client")

    initiated = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "init_creation_of_payment_method"),
        wallet_id=wallet_id,
        wallet_name=faker.word(),
        user_id=user_id,
        user_name=faker.name(),
        user_email=faker.email(),
    )

    assert isinstance(initiated, PaymentMethodInitiated)

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "init_payment_method"
        ].called

    cancelled = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "cancel_creation_of_payment_method"),
        payment_method_id=initiated.payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else 5,
    )

    assert cancelled is None

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "delete_payment_method"
        ].called


@pytest.mark.testit
async def test_webserver_crud_payment_method_workflow(
    is_pdb_enabled: bool,
    app: FastAPI,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mock_payments_gateway_service_or_none: MockRouter | None,
    faker: Faker,
    payments_clean_db: None,
):
    assert app
    user_id = faker.pyint()
    wallet_id = faker.pyint()

    rpc_client = await rabbitmq_rpc_client("web-server-client")

    inited = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "init_creation_of_payment_method"),
        wallet_id=wallet_id,
        wallet_name=faker.word(),
        user_id=user_id,
        user_name=faker.name(),
        user_email=faker.email(),
    )

    assert isinstance(inited, PaymentMethodInitiated)

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "init_payment_method"
        ].called

    # Faking ACK----
    repo = PaymentsMethodsRepo(app.state.engine)
    await repo.update_ack_payment_method(
        inited.payment_method_id,
        completion_state=InitPromptAckFlowState.SUCCESS,
        state_message="FAKED ACK",
    )
    # -----

    listed = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "list_payment_methods"),
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else 5,
    )
    assert len(listed) == 1

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "batch_get_payment_methods"
        ].called

    got = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "get_payment_method"),
        payment_method_id=inited.payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else 5,
    )
    assert got == listed[0]
    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes["get_payment_method"].called

    await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "delete_payment_method"),
        payment_method_id=inited.payment_method_id,
        user_id=user_id,
        wallet_id=wallet_id,
        timeout_s=None if is_pdb_enabled else 5,
    )

    if mock_payments_gateway_service_or_none:
        assert mock_payments_gateway_service_or_none.routes[
            "delete_payment_method"
        ].called
