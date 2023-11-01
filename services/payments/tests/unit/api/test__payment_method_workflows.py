# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any

import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from models_library.api_schemas_webserver.wallets import PaymentMethodInitiated
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient
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
def init_payment_method_kwargs(faker: Faker) -> dict[str, Any]:
    return {
        "wallet_id": faker.pyint(),
        "wallet_name": faker.word(),
        "user_id": faker.pyint(),
        "user_name": faker.name(),
        "user_email": faker.email(),
    }


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4715"
)
async def test_successful_create_payment_method_workflow(
    app: FastAPI,
    client: httpx.AsyncClient,
    faker: Faker,
    rpc_client: RabbitMQRPCClient,
    mock_payments_gateway_service_or_none: MockRouter | None,
    init_payment_method_kwargs: dict[str, Any],
    auth_headers: dict[str, str],
    payments_clean_db: None,
    mocker: MockerFixture,
):
    if mock_payments_gateway_service_or_none is None:
        pytest.skip("cannot run thist test against external because we ACK here")

    mock_on_payment_method_completed = mocker.patch(
        "simcore_service_payments.api.rest._acknowledgements.payments_methods.on_payment_method_completed",
        autospec=True,
    )

    # INIT via api/rpc
    inited = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        parse_obj_as(RPCMethodName, "init_creation_of_payment_method"),
        **init_payment_method_kwargs,
        timeout_s=None,  # for debug
    )

    assert isinstance(inited, PaymentMethodInitiated)
    assert mock_payments_gateway_service_or_none.routes["init_payment"].called

    # ACK via api/rest
    response = await client.post(
        f"/v1/payments-methods/{inited.payment_method_id}:ack",
        json=AckPayment(success=True, invoice_url=faker.url()).dict(),
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert mock_on_payment_method_completed.called
