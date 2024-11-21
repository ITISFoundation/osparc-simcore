# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import httpx
import pytest
from faker import Faker
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_webserver.wallets import WalletPaymentInitiated
from models_library.basic_types import IDStr
from models_library.payments import UserInvoiceAddress
from models_library.products import StripePriceID, StripeTaxRateID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import EmailStr, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq._constants import RPC_REQUEST_DEFAULT_TIMEOUT_S
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


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/osparc-simcore/pull/4715"
)
async def test_successful_one_time_payment_workflow(
    is_pdb_enabled: bool,
    app: FastAPI,
    client: httpx.AsyncClient,
    faker: Faker,
    rpc_client: RabbitMQRPCClient,
    mock_payments_gateway_service_or_none: MockRouter | None,
    wallet_id: WalletID,
    wallet_name: IDStr,
    user_id: UserID,
    user_name: IDStr,
    user_email: EmailStr,
    product_price_stripe_price_id: StripePriceID,
    product_price_stripe_tax_rate_id: StripeTaxRateID,
    auth_headers: dict[str, str],
    payments_clean_db: None,
    mocker: MockerFixture,
):
    if mock_payments_gateway_service_or_none is None:
        pytest.skip("cannot run thist test against external because we ACK here")

    mock_on_payment_completed = mocker.patch(
        "simcore_service_payments.api.rest._acknowledgements.payments.on_payment_completed",
        autospec=True,
    )

    # ACK via api/rest
    inited = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("init_payment"),
        amount_dollars=1000,
        target_credits=10000,
        product_name="osparc",
        wallet_id=wallet_id,
        wallet_name=wallet_name,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        user_address=UserInvoiceAddress(country="CH"),
        stripe_price_id=product_price_stripe_price_id,
        stripe_tax_rate_id=product_price_stripe_tax_rate_id,
        timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    assert isinstance(inited, WalletPaymentInitiated)
    assert mock_payments_gateway_service_or_none.routes["init_payment"].called

    # ACK
    response = await client.post(
        f"/v1/payments/{inited.payment_id}:ack",
        json=jsonable_encoder(
            AckPayment(success=True, invoice_url=faker.url()).model_dump()
        ),
        headers=auth_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    assert mock_on_payment_completed.called

    # LIST payments via api/rest
    got = await rpc_client.request(
        PAYMENTS_RPC_NAMESPACE,
        TypeAdapter(RPCMethodName).validate_python("get_payments_page"),
        user_id=user_id,
        product_name="osparc",
        timeout_s=None if is_pdb_enabled else RPC_REQUEST_DEFAULT_TIMEOUT_S,
    )

    total_number_of_items, transactions = got
    assert total_number_of_items == 1
    assert len(transactions) == 1

    assert transactions[0].state == "SUCCESS"
    assert transactions[0].payment_id == inited.payment_id
