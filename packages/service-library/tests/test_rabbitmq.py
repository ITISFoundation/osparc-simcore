# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-statements


import asyncio
from typing import AsyncIterator, Callable
from unittest import mock

import aio_pika
import pytest
from attr import dataclass
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
def random_exchange_name(faker: Faker) -> Callable[[], str]:
    def _creator() -> str:
        return f"pytest_fake_exchange_{faker.pystr()}"

    return _creator


@pytest.fixture
def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock(return_value=True)


@dataclass(frozen=True)
class PytestRabbitMessage:
    message: str

    def topic(self) -> str:
        return "pytest.red"

    def body(self) -> bytes:
        return self.message.encode()


@pytest.fixture
def random_rabbit_message(faker: Faker) -> Callable[[], PytestRabbitMessage]:
    def _creator() -> PytestRabbitMessage:
        return PytestRabbitMessage(message=faker.text())

    return _creator


async def _assert_message_received(
    mocked_message_parser: mock.AsyncMock,
    expected_call_count: int,
    expected_message: PytestRabbitMessage,
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
                mocked_message_parser.assert_called_once_with(
                    expected_message.message.encode()
                )
            elif expected_call_count == 0:
                mocked_message_parser.assert_not_called()
            else:
                mocked_message_parser.assert_called_with(
                    expected_message.message.encode()
                )


async def test_rabbit_client_pub_sub_message_is_lost_if_no_consumer_present(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message()

    exchange_name = random_exchange_name()
    await publisher.publish(exchange_name, message)
    await asyncio.sleep(0)  # ensure context switch
    await consumer.subscribe(exchange_name, mocked_message_parser)
    await _assert_message_received(mocked_message_parser, 0, message)


async def test_rabbit_client_pub_sub(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message()

    exchange_name = random_exchange_name()
    await consumer.subscribe(exchange_name, mocked_message_parser)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)


@pytest.mark.parametrize("num_subs", [10])
async def test_rabbit_client_pub_many_subs(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
    num_subs: int,
):
    consumers = (rabbitmq_client(f"consumer_{n}") for n in range(num_subs))
    mocked_message_parsers = [
        mocker.AsyncMock(return_value=True) for _ in range(num_subs)
    ]

    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message()
    exchange_name = random_exchange_name()
    await asyncio.gather(
        *(
            consumer.subscribe(exchange_name, parser)
            for consumer, parser in zip(consumers, mocked_message_parsers)
        )
    )

    await publisher.publish(exchange_name, message)
    await asyncio.gather(
        *(
            _assert_message_received(parser, 1, message)
            for parser in mocked_message_parsers
        )
    )


async def test_rabbit_client_pub_sub_republishes_if_exception_raised(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
):
    publisher = rabbitmq_client("publisher")
    consumer = rabbitmq_client("consumer")

    message = random_rabbit_message()

    def _raise_once_then_true(*args, **kwargs):
        _raise_once_then_true.calls += 1

        if _raise_once_then_true.calls == 1:
            raise KeyError("this is a test!")
        if _raise_once_then_true.calls == 2:
            return False
        return True

    exchange_name = random_exchange_name()
    _raise_once_then_true.calls = 0
    mocked_message_parser.side_effect = _raise_once_then_true
    await consumer.subscribe(exchange_name, mocked_message_parser)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 3, message)


@pytest.mark.parametrize("num_subs", [10])
async def test_pub_sub_with_non_exclusive_queue(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
    num_subs: int,
):
    consumers = (rabbitmq_client(f"consumer_{n}") for n in range(num_subs))
    mocked_message_parsers = [
        mocker.AsyncMock(return_value=True) for _ in range(num_subs)
    ]

    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message()
    exchange_name = random_exchange_name()
    await asyncio.gather(
        *(
            consumer.subscribe(exchange_name, parser, exclusive_queue=False)
            for consumer, parser in zip(consumers, mocked_message_parsers)
        )
    )

    await publisher.publish(exchange_name, message)
    # only one consumer should have gotten the message here and the others not
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            total_call_count = 0
            for parser in mocked_message_parsers:
                total_call_count += parser.call_count
            assert total_call_count == 1, "too many messages"


def test_rabbit_pub_sub_performance(
    benchmark,
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
):
    consumer = rabbitmq_client("consumer")
    publisher = rabbitmq_client("publisher")
    message = random_rabbit_message()

    exchange_name = random_exchange_name()
    asyncio.get_event_loop().run_until_complete(
        consumer.subscribe(exchange_name, mocked_message_parser)
    )

    async def async_fct_to_test():
        await publisher.publish(exchange_name, message)
        await _assert_message_received(mocked_message_parser, 1, message)
        mocked_message_parser.reset_mock()

    def run_test_async():
        asyncio.get_event_loop().run_until_complete(async_fct_to_test())

    benchmark.pedantic(run_test_async, iterations=1, rounds=10)


async def test_rabbit_pub_sub_with_topic(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
):
    exchange_name = f"{random_exchange_name()}_topic"
    message = random_rabbit_message()
    message1_topic = "pytest.red.critical"
    message2_topic = "pytest.orange.debug"
    publisher = rabbitmq_client("publisher")

    all_receiving_consumer = rabbitmq_client("all_receiving_consumer")
    all_receiving_mocked_message_parser = mocker.AsyncMock(return_value=True)
    await all_receiving_consumer.subscribe(
        exchange_name, all_receiving_mocked_message_parser, topics=["#"]
    )

    only_critical_consumer = rabbitmq_client("only_critical_consumer")
    only_critical_mocked_message_parser = mocker.AsyncMock(return_value=True)
    await only_critical_consumer.subscribe(
        exchange_name, only_critical_mocked_message_parser, topics=["*.*.critical"]
    )

    orange_and_critical_consumer = rabbitmq_client("orange_and_critical_consumer")
    orange_and_critical_mocked_message_parser = mocker.AsyncMock(return_value=True)
    await orange_and_critical_consumer.subscribe(
        exchange_name,
        orange_and_critical_mocked_message_parser,
        topics=["*.*.critical", "*.orange.*"],
    )

    # check now that topic is working
    await publisher.publish(exchange_name, message, topic=message1_topic)
    await publisher.publish(exchange_name, message, topic=message2_topic)

    await _assert_message_received(all_receiving_mocked_message_parser, 2, message)
    await _assert_message_received(only_critical_mocked_message_parser, 1, message)
    await _assert_message_received(
        orange_and_critical_mocked_message_parser, 2, message
    )


async def test_rabbit_pub_sub_bind_and_unbind_topics(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
):
    exchange_name = f"{random_exchange_name()}_topic"
    message = random_rabbit_message()
    publisher = rabbitmq_client("publisher")
    consumer = rabbitmq_client("consumer")
    # send some messages
    await publisher.publish(exchange_name, message, topic="faker.debug")
    await publisher.publish(exchange_name, message, topic="faker.info")
    await publisher.publish(exchange_name, message, topic="faker.warning")
    await publisher.publish(exchange_name, message, topic="faker.critical")

    # we should get no messages since no one was subscribed
    queue_name = await consumer.subscribe(
        exchange_name, mocked_message_parser, topics=[]
    )
    await _assert_message_received(mocked_message_parser, 0, message)

    # now we should also not get anything since we are not interested in any topic
    await publisher.publish(exchange_name, message, topic="faker.debug")
    await publisher.publish(exchange_name, message, topic="faker.info")
    await publisher.publish(exchange_name, message, topic="faker.warning")
    await publisher.publish(exchange_name, message, topic="faker.critical")
    await _assert_message_received(mocked_message_parser, 0, message)

    await consumer.add_topics(
        exchange_name, queue_name, topics=["*.warning", "*.critical"]
    )
    await publisher.publish(exchange_name, message, topic="faker.debug")
    await publisher.publish(exchange_name, message, topic="faker.info")
    await publisher.publish(exchange_name, message, topic="faker.warning")
    await publisher.publish(exchange_name, message, topic="faker.critical")
    await _assert_message_received(mocked_message_parser, 2, message)
    mocked_message_parser.reset_mock()
    # adding again the same topics makes no difference, we should still have 2 messages
    await consumer.add_topics(exchange_name, queue_name, topics=["*.warning"])
    await publisher.publish(exchange_name, message, topic="faker.debug")
    await publisher.publish(exchange_name, message, topic="faker.info")
    await publisher.publish(exchange_name, message, topic="faker.warning")
    await publisher.publish(exchange_name, message, topic="faker.critical")
    await _assert_message_received(mocked_message_parser, 2, message)
    mocked_message_parser.reset_mock()

    # after unsubscribing, we do not receive warnings anymore
    await consumer.remove_topics(exchange_name, queue_name, topics=["*.warning"])
    await publisher.publish(exchange_name, message, topic="faker.debug")
    await publisher.publish(exchange_name, message, topic="faker.info")
    await publisher.publish(exchange_name, message, topic="faker.warning")
    await publisher.publish(exchange_name, message, topic="faker.critical")
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()

    # after unsubscribing something that does not exist, we still receive the same things
    await consumer.remove_topics(exchange_name, queue_name, topics=[])
    await publisher.publish(exchange_name, message, topic="faker.debug")
    await publisher.publish(exchange_name, message, topic="faker.info")
    await publisher.publish(exchange_name, message, topic="faker.warning")
    await publisher.publish(exchange_name, message, topic="faker.critical")
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()

    # after unsubscribing we receive nothing anymore
    await consumer.unsubscribe(queue_name)
    await publisher.publish(exchange_name, message, topic="faker.debug")
    await publisher.publish(exchange_name, message, topic="faker.info")
    await publisher.publish(exchange_name, message, topic="faker.warning")
    await publisher.publish(exchange_name, message, topic="faker.critical")
    await _assert_message_received(mocked_message_parser, 0, message)


async def test_rabbit_not_using_the_same_exchange_type_raises(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
):
    exchange_name = f"{random_exchange_name()}_fanout"
    client = rabbitmq_client("consumer")
    # this will create a FANOUT exchange
    await client.subscribe(exchange_name, mocked_message_parser)
    # now do a second subscribtion wiht topics, will create a TOPICS exchange
    with pytest.raises(aio_pika.exceptions.ChannelPreconditionFailed):
        await client.subscribe(exchange_name, mocked_message_parser, topics=[])


async def test_rabbit_adding_topics_to_a_fanout_exchange(
    rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[[], PytestRabbitMessage],
):
    exchange_name = f"{random_exchange_name()}_fanout"
    message = random_rabbit_message()
    publisher = rabbitmq_client("publisher")
    consumer = rabbitmq_client("consumer")
    queue_name = await consumer.subscribe(exchange_name, mocked_message_parser)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()
    # this changes nothing on a FANOUT exchange
    await consumer.add_topics(exchange_name, queue_name, topics=["some_topics"])
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()
    # this changes nothing on a FANOUT exchange
    await consumer.remove_topics(exchange_name, queue_name, topics=["some_topics"])
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()
    # this will do something
    await consumer.unsubscribe(queue_name)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 0, message)
