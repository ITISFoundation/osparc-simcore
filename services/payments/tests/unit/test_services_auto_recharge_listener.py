# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest import mock

import pytest
import sqlalchemy as sa
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver import DEFAULT_WEBSERVER_RPC_NAMESPACE
from models_library.api_schemas_webserver.wallets import (
    GetWalletAutoRecharge,
    PaymentMethodID,
)
from models_library.basic_types import NonNegativeDecimal
from models_library.payments import InvoiceDataGet
from models_library.products import ProductName
from models_library.rabbitmq_messages import WalletCreditsMessage
from models_library.users import UserID
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.faker_factories import (
    random_payment_autorecharge,
    random_payment_method,
    random_payment_transaction,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx import MockRouter
from servicelib.rabbitmq import RabbitMQClient, RabbitMQRPCClient, RPCRouter
from simcore_postgres_database.models.payments_autorecharge import payments_autorecharge
from simcore_postgres_database.models.payments_methods import payments_methods
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
    payments_transactions,
)
from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.db.payments_transactions_repo import (
    PaymentsTransactionsRepo,
)
from simcore_service_payments.models.db import PaymentsTransactionsDB
from simcore_service_payments.models.schemas.acknowledgements import (
    AckPaymentWithPaymentMethod,
)
from simcore_service_payments.services.auto_recharge_process_message import (
    _check_autorecharge_conditions_not_met,
    _check_wallet_credits_above_threshold,
    _exceeds_monthly_limit,
    _is_message_too_old,
    _was_wallet_topped_up_recently,
)
from tenacity.asyncio import AsyncRetrying
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
    external_envfile_dict: EnvVarsDict,
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
            **external_envfile_dict,
            "POSTGRES_CLIENT_NAME": "payments-service-pg-client",
            "PAYMENTS_AUTORECHARGE_ENABLED": "1",
        },
    )


@pytest.fixture
async def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        "simcore_service_payments.services.auto_recharge_listener.process_message"
    )


async def test_process_message__called(
    mocked_message_parser: mock.AsyncMock,
    app: FastAPI,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
):
    publisher = create_rabbitmq_client("publisher")
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
        _completed_at = datetime.now(tz=UTC) + timedelta(minutes=1)

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
async def mocked_pay_with_payment_method(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.patch(
        "simcore_service_payments.services.payments.PaymentsGatewayApi.pay_with_payment_method",
        return_value=AckPaymentWithPaymentMethod.model_construct(
            **AckPaymentWithPaymentMethod.model_config["json_schema_extra"]["example"]
        ),
    )


@pytest.fixture
async def mock_rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("client")

    # mock returned client
    mocker.patch(
        "simcore_service_payments.services.auto_recharge_process_message.get_rabbitmq_rpc_client",
        return_value=rpc_client,
    )

    return rpc_client


@pytest.fixture
async def mock_rpc_server(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
    mocker: MockerFixture,
) -> RabbitMQRPCClient:
    rpc_server = await rabbitmq_rpc_client("mock_server")

    router = RPCRouter()

    # mocks the interface defined in the webserver

    @router.expose()
    async def get_invoice_data(
        user_id: UserID,
        dollar_amount: Decimal,
        product_name: ProductName,
    ) -> InvoiceDataGet:
        return InvoiceDataGet.model_validate(
            InvoiceDataGet.model_config["json_schema_extra"]["examples"][0]
        )

    await rpc_server.register_router(router, namespace=DEFAULT_WEBSERVER_RPC_NAMESPACE)

    return rpc_server


async def _assert_payments_transactions_db_row(postgres_db) -> PaymentsTransactionsDB:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.2),
        stop=stop_after_delay(10),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt, postgres_db.connect() as con:
            result = con.execute(sa.select(payments_transactions))
            row = result.first()
            assert row
            return PaymentsTransactionsDB.model_validate(row)


async def test_process_message__whole_autorecharge_flow_success(
    app: FastAPI,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    wallet_id: int,
    populate_test_db: None,
    mocked_pay_with_payment_method: mock.AsyncMock,
    mock_rpc_server: RabbitMQRPCClient,
    mock_rpc_client: RabbitMQRPCClient,
    mock_resoruce_usage_tracker_service_api: MockRouter,
    postgres_db: sa.engine.Engine,
):
    publisher = create_rabbitmq_client("publisher")
    msg = WalletCreditsMessage(
        wallet_id=wallet_id, credits=Decimal(80.5), product_name="s4l"
    )
    await publisher.publish(WalletCreditsMessage.get_channel_name(), msg)

    row = await _assert_payments_transactions_db_row(postgres_db)
    assert row.wallet_id == wallet_id
    assert row.state == PaymentTransactionState.SUCCESS
    assert row.comment == "Payment generated by auto recharge"
    assert len(mock_resoruce_usage_tracker_service_api.calls) == 1


@pytest.mark.parametrize(
    "_credits,expected", [(Decimal(10001), True), (Decimal(9999), False)]
)
async def test_check_wallet_credits_above_threshold(
    app: FastAPI, _credits: Decimal, expected: bool
):
    settings: ApplicationSettings = app.state.settings
    assert settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT

    assert expected == await _check_wallet_credits_above_threshold(
        settings.PAYMENTS_AUTORECHARGE_DEFAULT_MONTHLY_LIMIT, _credits
    )


@pytest.mark.parametrize(
    "get_wallet_auto_recharge,expected",
    [
        (
            GetWalletAutoRecharge(
                enabled=True,
                payment_method_id=PaymentMethodID("123"),
                min_balance_in_credits=NonNegativeDecimal(10),
                top_up_amount_in_usd=NonNegativeDecimal(10),
                monthly_limit_in_usd=NonNegativeDecimal(10),
            ),
            False,
        ),
        (
            GetWalletAutoRecharge(
                enabled=False,
                payment_method_id=PaymentMethodID("123"),
                min_balance_in_credits=NonNegativeDecimal(10),
                top_up_amount_in_usd=NonNegativeDecimal(10),
                monthly_limit_in_usd=NonNegativeDecimal(10),
            ),
            True,
        ),
        (
            GetWalletAutoRecharge(
                enabled=True,
                payment_method_id=None,
                min_balance_in_credits=NonNegativeDecimal(10),
                top_up_amount_in_usd=NonNegativeDecimal(10),
                monthly_limit_in_usd=NonNegativeDecimal(10),
            ),
            True,
        ),
        (None, True),
    ],
)
async def test_check_autorecharge_conditions_not_met(
    app: FastAPI, get_wallet_auto_recharge: GetWalletAutoRecharge, expected: bool
):
    assert expected == await _check_autorecharge_conditions_not_met(
        get_wallet_auto_recharge
    )


@pytest.fixture()
def populate_payment_transaction_db(
    postgres_db: sa.engine.Engine, wallet_id: int
) -> Iterator[None]:
    with postgres_db.connect() as con:
        con.execute(
            payments_transactions.insert().values(
                **random_payment_transaction(
                    price_dollars=Decimal(9500),
                    wallet_id=wallet_id,
                    state=PaymentTransactionState.SUCCESS,
                    completed_at=datetime.now(tz=UTC),
                    initiated_at=datetime.now(tz=UTC) - timedelta(seconds=10),
                )
            )
        )

        yield

        con.execute(payments_transactions.delete())


@pytest.mark.parametrize(
    "get_wallet_auto_recharge,expected",
    [
        (
            GetWalletAutoRecharge(
                enabled=True,
                payment_method_id=PaymentMethodID("123"),
                min_balance_in_credits=NonNegativeDecimal(10),
                top_up_amount_in_usd=NonNegativeDecimal(300),
                monthly_limit_in_usd=NonNegativeDecimal(10000),
            ),
            False,
        ),
        (
            GetWalletAutoRecharge(
                enabled=False,
                payment_method_id=PaymentMethodID("123"),
                min_balance_in_credits=NonNegativeDecimal(10),
                top_up_amount_in_usd=NonNegativeDecimal(1000),
                monthly_limit_in_usd=NonNegativeDecimal(10000),
            ),
            True,
        ),
    ],
)
async def test_exceeds_monthly_limit(
    app: FastAPI,
    wallet_id: int,
    populate_payment_transaction_db: None,
    get_wallet_auto_recharge: GetWalletAutoRecharge,
    expected: bool,
):
    _payments_transactions_repo = PaymentsTransactionsRepo(db_engine=app.state.engine)

    assert expected == await _exceeds_monthly_limit(
        _payments_transactions_repo, wallet_id, get_wallet_auto_recharge
    )


async def test_was_wallet_topped_up_recently_true(
    app: FastAPI,
    wallet_id: int,
    populate_payment_transaction_db: None,
):
    _payments_transactions_repo = PaymentsTransactionsRepo(db_engine=app.state.engine)

    assert (
        await _was_wallet_topped_up_recently(_payments_transactions_repo, wallet_id)
        is True
    )


@pytest.fixture()
def populate_payment_transaction_db_with_older_trans(
    postgres_db: sa.engine.Engine, wallet_id: int
) -> Iterator[None]:
    with postgres_db.connect() as con:
        current_timestamp = datetime.now(tz=UTC)
        current_timestamp_minus_10_minutes = current_timestamp - timedelta(minutes=10)

        con.execute(
            payments_transactions.insert().values(
                **random_payment_transaction(
                    price_dollars=Decimal(9500),
                    wallet_id=wallet_id,
                    state=PaymentTransactionState.SUCCESS,
                    initiated_at=current_timestamp_minus_10_minutes,
                )
            )
        )

        yield

        con.execute(payments_transactions.delete())


async def test_was_wallet_topped_up_recently_false(
    app: FastAPI,
    wallet_id: int,
    populate_payment_transaction_db_with_older_trans: None,
):
    _payments_transactions_repo = PaymentsTransactionsRepo(db_engine=app.state.engine)

    assert (
        await _was_wallet_topped_up_recently(_payments_transactions_repo, wallet_id)
        is False
    )


async def test__is_message_too_old_true():
    _dummy_message_timestamp = datetime.now(tz=UTC) - timedelta(minutes=10)

    assert await _is_message_too_old(_dummy_message_timestamp) is True


async def test__is_message_too_old_false():
    _dummy_message_timestamp = datetime.now(tz=UTC) - timedelta(minutes=3)

    assert await _is_message_too_old(_dummy_message_timestamp) is False
