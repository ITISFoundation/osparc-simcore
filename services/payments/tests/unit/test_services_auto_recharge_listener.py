# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Awaitable, Iterator
from unittest import mock

import pytest
import sqlalchemy as sa
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver import WEBSERVER_RPC_NAMESPACE
from models_library.products import CreditResultGet, ProductName
from models_library.rabbitmq_messages import WalletCreditsMessage
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.rawdata_fakers import (
    random_payment_autorecharge,
    random_payment_method,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient, RPCRouter
from simcore_postgres_database.models.payments_autorecharge import payments_autorecharge
from simcore_postgres_database.models.payments_methods import payments_methods
from simcore_service_payments.models.payments_gateway import GetPaymentMethod
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

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


@pytest.fixture
async def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        "simcore_service_payments.services.auto_recharge_listener.process_message"
    )


async def test_process_event_function_called(
    mocked_message_parser: mock.AsyncMock,
    app: FastAPI,
    rabbitmq_client: Callable[[str], RabbitMQClient],
):
    publisher = rabbitmq_client("publisher")
    msg = WalletCreditsMessage(wallet_id=1, credits=Decimal(80.5), product_name="s4l")
    await publisher.publish(WalletCreditsMessage.get_channel_name(), msg)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            mocked_message_parser.assert_called_once()


@pytest.fixture()
def populate_test_db(
    postgres_db: sa.engine.Engine, faker: Faker, wallet_id: int
) -> Iterator[None]:
    with postgres_db.connect() as con:
        _primary_payment_method_id = faker.uuid4()
        _completed_at = datetime.now(tz=timezone.utc) + timedelta(minutes=1)

        con.execute(
            payments_methods.insert().values(
                **random_payment_method(
                    payment_method_id=_primary_payment_method_id,
                    wallet_id=wallet_id,
                    state="SUCCESS",
                    completed_at=_completed_at,
                )
            )
        )
        con.execute(
            payments_autorecharge.insert().values(
                **random_payment_autorecharge(
                    primary_payment_method_id=_primary_payment_method_id,
                    wallet_id=wallet_id,
                )
            )
        )

        yield

        con.execute(payments_methods.delete())
        con.execute(payments_autorecharge.delete())


@pytest.fixture()
def wallet_id(faker: Faker):
    return faker.pyint()


@pytest.fixture
async def mocked_get_payment_method(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        "simcore_service_payments.services.payments_methods.PaymentsGatewayApi.get_payment_method",
        return_value=GetPaymentMethod.construct(
            **GetPaymentMethod.Config.schema_extra["examples"][0]
        ),
    )


@pytest.fixture
async def mock_rpc_server(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("client")
    rpc_server = await rabbitmq_rpc_client("mock_server")

    router = RPCRouter()

    # mocks the interface defined in the webserver

    @router.expose()
    async def get_credit_amount(
        dollar_amount: ProductName, product_name: ProductName
    ) -> CreditResultGet:
        return CreditResultGet.parse_obj(
            CreditResultGet.Config.schema_extra["examples"][0]
        )

    await rpc_server.register_router(router, namespace=WEBSERVER_RPC_NAMESPACE)

    # mock returned client
    mocker.patch(
        "simcore_service_payments.services.auto_recharge_process_message.get_rabbitmq_rpc_client",
        return_value=rpc_client,
    )

    return rpc_client


async def test_process_event_function_autorecharge_flow(
    app: FastAPI,
    rabbitmq_client: Callable[[str], RabbitMQClient],
    wallet_id: int,
    populate_test_db: None,
    mocked_get_payment_method: mock.AsyncMock,
    mock_rpc_server: RabbitMQRPCClient,
):
    publisher = rabbitmq_client("publisher")
    msg = WalletCreditsMessage(
        wallet_id=wallet_id, credits=Decimal(80.5), product_name="s4l"
    )
    await publisher.publish(WalletCreditsMessage.get_channel_name(), msg)

    await asyncio.sleep(20)
    # async for attempt in AsyncRetrying(
    #     wait=wait_fixed(0.1),
    #     stop=stop_after_delay(5),
    #     retry=retry_if_exception_type(AssertionError),
    #     reraise=True,
    # ):
    #     with attempt:
    #         assert 2 == 1
