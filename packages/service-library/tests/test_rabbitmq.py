# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import asyncio
from typing import AsyncIterator, Callable
from unittest import mock

import pytest
from faker import Faker
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import RabbitMQClient
from settings_library.rabbit import RabbitSettings
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def rabbit_client_name(faker: Faker) -> str:
    return faker.pystr()


async def test_rabbit_client(rabbit_client_name: str, rabbit_service: RabbitSettings):
    client = RabbitMQClient(rabbit_client_name, rabbit_service)
    assert client
    # check it is correctly initialized
    assert client._connection_pool
    assert not client._connection_pool.is_closed
    assert client._channel_pool
    assert not client._channel_pool.is_closed
    assert client.client_name == rabbit_client_name
    assert client.settings == rabbit_service
    await client.close()
    assert client._connection_pool
    assert client._connection_pool.is_closed
    assert client._channel_pool
    assert client._channel_pool.is_closed


@pytest.fixture
async def rabbitmq_client(
    rabbit_service: RabbitSettings,
) -> AsyncIterator[Callable[[str], RabbitMQClient]]:
    created_clients = []

    def _creator(client_name: str) -> RabbitMQClient:
        client = RabbitMQClient(f"pytest_{client_name}", rabbit_service)
        assert client
        assert client._connection_pool
        assert not client._connection_pool.is_closed
        assert client._channel_pool
        assert not client._channel_pool.is_closed
        assert client.client_name == f"pytest_{client_name}"
        assert client.settings == rabbit_service
        created_clients.append(client)
        return client

    yield _creator
    # cleanup, properly close the clients
    await asyncio.gather(*(client.close() for client in created_clients))
    for client in created_clients:
        assert client._channel_pool
        assert client._channel_pool.is_closed


@pytest.fixture
def random_exchange_name(faker: Faker) -> str:
    return f"pytest_fake_exchange_{faker.pystr()}"


async def _assert_message_received(
    mocked_message_parser: mock.AsyncMock,
    expected_call_count: int,
    expected_message: str,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            # NOTE: this sleep is here to ensure that there are not multiple messages coming in
            await asyncio.sleep(1)
            assert mocked_message_parser.call_count == expected_call_count
            if expected_call_count == 1:
                mocked_message_parser.assert_called_once_with(expected_message.encode())
            elif expected_call_count == 0:
                mocked_message_parser.assert_not_called()
            else:
                mocked_message_parser.assert_called_with(expected_message.encode())


async def test_rabbit_client_pub_sub_message_is_lost_if_no_consumer_present(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: str,
    mocker: MockerFixture,
    faker: Faker,
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")

    message = faker.text()

    mocked_message_parser = mocker.AsyncMock(return_value=True)
    await publisher.publish(random_exchange_name, message)
    await consumer.consume(random_exchange_name, mocked_message_parser)
    await _assert_message_received(mocked_message_parser, 0, "")


async def test_rabbit_client_pub_sub(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: str,
    mocker: MockerFixture,
    faker: Faker,
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")

    message = faker.text()

    mocked_message_parser = mocker.AsyncMock(return_value=True)
    await consumer.consume(random_exchange_name, mocked_message_parser)
    await publisher.publish(random_exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)


@pytest.mark.parametrize("num_subs", [10])
async def test_rabbit_client_pub_many_subs(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: str,
    mocker: MockerFixture,
    faker: Faker,
    num_subs: int,
):
    consumers = (rabbitmq_client(f"consumer_{n}") for n in range(num_subs))
    mocked_message_parsers = (
        mocker.AsyncMock(return_value=True) for _ in range(num_subs)
    )

    publisher = rabbitmq_client("publisher")
    message = faker.text()

    await asyncio.gather(
        *(
            consumer.consume(random_exchange_name, parser)
            for consumer, parser in zip(consumers, mocked_message_parsers)
        )
    )

    await publisher.publish(random_exchange_name, message)
    await asyncio.gather(
        *(
            _assert_message_received(parser, 1, message)
            for parser in mocked_message_parsers
        )
    )


async def test_rabbit_client_pub_sub_republishes_if_exception_raised(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: str,
    mocker: MockerFixture,
    faker: Faker,
):
    publisher = rabbitmq_client("publisher")
    consumer = rabbitmq_client("consumer")

    message = faker.text()

    def _raise_once_then_true(*args, **kwargs):
        _raise_once_then_true.calls += 1

        if _raise_once_then_true.calls == 1:
            raise KeyError("this is a test!")
        if _raise_once_then_true.calls == 2:
            return False
        return True

    _raise_once_then_true.calls = 0
    mocked_message_parser = mocker.AsyncMock(side_effect=_raise_once_then_true)
    await consumer.consume(random_exchange_name, mocked_message_parser)
    await publisher.publish(random_exchange_name, message)
    await _assert_message_received(mocked_message_parser, 3, message)
