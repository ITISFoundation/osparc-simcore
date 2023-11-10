# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from decimal import Decimal
from unittest import mock

import pytest
from fastapi import FastAPI
from models_library.rabbitmq_messages import WalletCreditsMessage
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from servicelib.rabbitmq import RabbitMQClient
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
    # return mocker.AsyncMock(return_value=True)
    return mocker.patch(
        "simcore_service_payments.services.auto_recharge_listener.process_message"
    )


async def test_process_event_functions(
    mocked_message_parser: mock.AsyncMock,
    app: FastAPI,
    rabbitmq_client: Callable[[str], RabbitMQClient],
):
    publisher = rabbitmq_client("publisher")
    msg = WalletCreditsMessage(wallet_id=1, credits=Decimal(120.5))
    await publisher.publish(WalletCreditsMessage.get_channel_name(), msg)

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            mocked_message_parser.assert_called_once()
