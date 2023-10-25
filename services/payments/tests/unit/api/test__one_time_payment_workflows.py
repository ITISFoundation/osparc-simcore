# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_webserver.wallets import WalletPaymentCreated
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName
from simcore_service_payments.api.rpc.routes import PAYMENTS_RPC_NAMESPACE
from simcore_service_payments.models.schemas.acknowledgements import AckPayment

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
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
        },
    )


@pytest.fixture
def init_payment_kwargs(faker: Faker) -> dict[str, Any]:
    return {
        "amount_dollars": 1000,
        "target_credits": 10000,
        "product_name": "osparc",
        "wallet_id": 1,
        "wallet_name": "wallet-name",
        "user_id": 1,
        "user_name": "user",
        "user_email": "user@email.com",
    }


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4715"
)
async def test_successful_one_time_payment_workflow(
    app: FastAPI,
    client: httpx.AsyncClient,
    faker: Faker,
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mock_payments_gateway_service_or_none: MockRouter | None,
    init_payment_kwargs: dict[str, Any],
    auth_headers: dict[str, str],
    payments_clean_db: None,
    mocker: MockerFixture,
):
    assert (
        mock_payments_gateway_service_or_none
    ), "cannot run against external because we ACK here"

    mock_on_payment_completed = mocker.patch(
        "simcore_service_payments.api.rest._acknowledgements.on_payment_completed",
        autospec=True,
    )

    rpc_client = await rabbitmq_rpc_client("web-server-client")

    # INIT
    result = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "init_payment"),
        **init_payment_kwargs,
        timeout_s=None,  # for debug
    )
    assert isinstance(result, WalletPaymentCreated)

    assert mock_payments_gateway_service_or_none.routes["init_payment"].called

    # ACK
    response = await client.post(
        f"/v1/payments/{result.payment_id}:ack",
        json=AckPayment(success=True, invoice_url=faker.url()).dict(),
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert mock_on_payment_completed.called
