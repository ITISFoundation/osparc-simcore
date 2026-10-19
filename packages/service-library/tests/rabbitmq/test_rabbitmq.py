# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-statements


import asyncio
import datetime
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final
from unittest import mock

import aio_pika
import pytest
from faker import Faker
from pydantic import PositiveFloat
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import (
    BIND_TO_ALL_TOPICS,
    ConsumerTag,
    QueueName,
    RabbitMQClient,
    _client,
)
from servicelib.rabbitmq._client import _DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS
from settings_library.rabbit import RabbitSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]

_ON_ERROR_DELAY_S: Final[float] = 0.1


@pytest.fixture
def rabbit_client_name(faker: Faker) -> str:
    return faker.pystr()


async def test_rabbit_client(
    rabbit_client_name: str,
    rabbit_service: RabbitSettings,
):
    client = RabbitMQClient(rabbit_client_name, rabbit_service)
    assert client
    # check it is correctly initialized
    assert client._connection_pool  # noqa: SLF001
    assert not client._connection_pool.is_closed  # noqa: SLF001
    assert client._channel_pool  # noqa: SLF001
    assert not client._channel_pool.is_closed  # noqa: SLF001
    assert client.client_name == rabbit_client_name
    assert client.settings == rabbit_service
    await client.close()
    assert client._connection_pool  # noqa: SLF001
    assert client._connection_pool.is_closed  # noqa: SLF001


@pytest.fixture
def mocked_message_parser(mocker: MockerFixture) -> mock.AsyncMock:
    return mocker.AsyncMock(return_value=True)


@dataclass(frozen=True)
class PytestRabbitMessage:
    message: str
    topic: str

    def routing_key(self) -> str:
        return self.topic

    def body(self) -> bytes:
        return self.message.encode()


@pytest.fixture
def random_rabbit_message(
    faker: Faker,
) -> Callable[..., PytestRabbitMessage]:
    def _creator(**kwargs: dict[str, Any]) -> PytestRabbitMessage:
        msg_config = {"message": faker.text(), "topic": None, **kwargs}

        return PytestRabbitMessage(**msg_config)

    return _creator


@pytest.fixture
def on_message_spy(mocker: MockerFixture) -> mock.Mock:
    return mocker.spy(_client, "_on_message")


def _get_spy_report(mock: mock.Mock) -> dict[str, set[int]]:
    results: dict[str, set[int]] = {}

    for entry in mock.call_args_list:
        message: aio_pika.abc.AbstractIncomingMessage = entry.args[2]
        assert message.routing_key is not None

        if message.routing_key not in results:
            results[message.routing_key] = set()

        count = _client._get_x_death_count(message)  # noqa: SLF001
        results[message.routing_key].add(count)

    return results


async def _setup_publisher_and_subscriber(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    max_requeue_retry: int,
    topics: list[str] | None,
    message_handler: Callable[[Any], Awaitable[bool]],
) -> int:
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")

    exchange_name = f"{random_exchange_name()}"

    await consumer.subscribe(
        exchange_name,
        message_handler,
        topics=topics,
        exclusive_queue=False,
        unexpected_error_max_attempts=max_requeue_retry,
        unexpected_error_retry_delay_s=_ON_ERROR_DELAY_S,
    )

    if topics is None:
        message = random_rabbit_message()
        await publisher.publish(exchange_name, message)
    else:
        for topic in topics:
            message = random_rabbit_message(topic=topic)
            await publisher.publish(exchange_name, message)

    topics_count: int = 1 if topics is None else len(topics)
    return topics_count


async def _assert_wait_for_messages(on_message_spy: mock.Mock, expected_results: int) -> None:
    total_seconds_to_wait = expected_results * _ON_ERROR_DELAY_S * 2
    print(f"Will wait for messages for {total_seconds_to_wait} seconds")
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(total_seconds_to_wait),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert len(on_message_spy.call_args_list) == expected_results

    # wait some more time to make sure retry mechanism did not trigger
    await asyncio.sleep(_ON_ERROR_DELAY_S * 3)
    assert len(on_message_spy.call_args_list) == expected_results


async def _assert_message_received(
    mocked_message_parser: mock.AsyncMock,
    expected_call_count: int,
    expected_message: PytestRabbitMessage | None = None,
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            print(
                f"--> waiting for rabbitmq message [{attempt.retry_state.attempt_number}, "
                f"{attempt.retry_state.idle_for}]"
            )
            assert mocked_message_parser.call_count == expected_call_count
            if expected_call_count == 1:
                assert expected_message
                mocked_message_parser.assert_called_once_with(expected_message.message.encode())
            elif expected_call_count == 0:
                mocked_message_parser.assert_not_called()
            else:
                assert expected_message
                mocked_message_parser.assert_any_call(expected_message.message.encode())
            print(
                f"<-- rabbitmq message received after [{attempt.retry_state.attempt_number}, "
                f"{attempt.retry_state.idle_for}]"
            )


_TOPICS: Final[list[list[str] | None]] = [
    None,
    ["one"],
    ["one", "two"],
]


@pytest.mark.parametrize("max_requeue_retry", [0, 1, 3, 10])
@pytest.mark.parametrize("topics", _TOPICS)
async def test_subscribe_to_failing_message_handler(
    on_message_spy: mock.Mock,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    max_requeue_retry: int,
    topics: list[str] | None,
):
    async def _faulty_message_handler(message: Any) -> bool:
        msg = f"Always fail. Received message {message}"
        raise RuntimeError(msg)

    topics_count = await _setup_publisher_and_subscriber(
        create_rabbitmq_client,
        random_exchange_name,
        random_rabbit_message,
        max_requeue_retry,
        topics,
        _faulty_message_handler,
    )

    expected_results = (max_requeue_retry + 1) * topics_count
    await _assert_wait_for_messages(on_message_spy, expected_results)

    report = _get_spy_report(on_message_spy)
    routing_keys: list[str] = [""] if topics is None else topics
    assert report == {k: set(range(max_requeue_retry + 1)) for k in routing_keys}


@pytest.mark.parametrize("topics", _TOPICS)
async def test_subscribe_fail_then_success(
    on_message_spy: mock.Mock,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    topics: list[str] | None,
):
    message_status: dict[str, bool] = {}

    async def _fail_once_then_succeed(message: Any) -> bool:
        if message not in message_status:
            message_status[message] = False
        if not message_status[message]:
            message_status[message] = True
            return False
        return True

    topics_count = await _setup_publisher_and_subscriber(
        create_rabbitmq_client,
        random_exchange_name,
        random_rabbit_message,
        _DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS,
        topics,
        _fail_once_then_succeed,
    )

    expected_results = 2 * topics_count
    await _assert_wait_for_messages(on_message_spy, expected_results)

    report = _get_spy_report(on_message_spy)
    routing_keys: list[str] = [""] if topics is None else topics
    assert report == {k: set(range(2)) for k in routing_keys}

    # check messages as expected
    original_message_count = 0
    requeued_message_count = 0
    for entry in on_message_spy.call_args_list:
        message = entry.args[2]
        if message.headers == {}:
            original_message_count += 1
        if message.headers and "x-death" in message.headers and message.headers["x-death"][0]["count"] == 1:
            requeued_message_count += 1

    assert original_message_count == topics_count
    assert requeued_message_count == topics_count


@pytest.mark.parametrize("topics", _TOPICS)
async def test_subscribe_always_returns_fails_stops(
    on_message_spy: mock.Mock,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    topics: list[str] | None,
):
    async def _always_returning_fail(_: Any) -> bool:
        return False

    topics_count = await _setup_publisher_and_subscriber(
        create_rabbitmq_client,
        random_exchange_name,
        random_rabbit_message,
        _DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS,
        topics,
        _always_returning_fail,
    )

    expected_results = (_DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS + 1) * topics_count
    await _assert_wait_for_messages(on_message_spy, expected_results)

    report = _get_spy_report(on_message_spy)
    routing_keys: list[str] = [""] if topics is None else topics
    assert report == {k: set(range(_DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS + 1)) for k in routing_keys}


@pytest.mark.parametrize("topics", _TOPICS)
@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors
async def test_publish_with_no_registered_subscriber(
    on_message_spy: mock.Mock,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    mocked_message_parser: mock.AsyncMock,
    topics: list[str] | None,
):
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")

    exchange_name = f"{random_exchange_name()}"

    ttl_s: float = 0.1
    topics_count: int = 1 if topics is None else len(topics)

    async def _publish_random_message() -> None:
        if topics is None:
            message = random_rabbit_message()
            await publisher.publish(exchange_name, message)

        else:
            for topic in topics:
                message = random_rabbit_message(topic=topic)
                await publisher.publish(exchange_name, message)

    async def _subscribe_consumer_to_queue() -> tuple[QueueName, ConsumerTag]:
        return await consumer.subscribe(
            exchange_name,
            mocked_message_parser,
            topics=topics,
            exclusive_queue=False,
            message_ttl=int(ttl_s * 1000),
            unexpected_error_max_attempts=_DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS,
            unexpected_error_retry_delay_s=ttl_s,
        )

    async def _unsubscribe_consumer(queue_name: QueueName, consumer_tag: ConsumerTag) -> None:
        await consumer.unsubscribe_consumer(queue_name, consumer_tag)

    # CASE 1 (subscribe immediately after publishing message)

    consumer_1 = await _subscribe_consumer_to_queue()
    await _unsubscribe_consumer(*consumer_1)
    await _publish_random_message()
    # reconnect immediately
    consumer_2 = await _subscribe_consumer_to_queue()
    # expected to receive a message (one per topic)
    await _assert_wait_for_messages(on_message_spy, 1 * topics_count)

    # CASE 2 (no subscriber attached when publishing)
    on_message_spy.reset_mock()

    await _unsubscribe_consumer(*consumer_2)
    await _publish_random_message()
    # wait for message to expire (will be dropped)
    await asyncio.sleep(ttl_s * 2)
    _consumer_3 = await _subscribe_consumer_to_queue()

    # wait for a message to be possibly delivered
    await asyncio.sleep(ttl_s * 2)
    # nothing changed from before
    await _assert_wait_for_messages(on_message_spy, 0)


async def test_rabbit_client_pub_sub_message_is_lost_if_no_consumer_present(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")
    message = random_rabbit_message()

    exchange_name = random_exchange_name()
    await publisher.publish(exchange_name, message)
    await asyncio.sleep(0)  # ensure context switch
    await consumer.subscribe(exchange_name, mocked_message_parser)
    await _assert_message_received(mocked_message_parser, 0)


async def test_rabbit_client_pub_sub(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")
    message = random_rabbit_message()

    exchange_name = random_exchange_name()
    await consumer.subscribe(exchange_name, mocked_message_parser)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)


@pytest.mark.parametrize("num_subs", [10])
async def test_rabbit_client_pub_many_subs(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    num_subs: int,
):
    consumers = (create_rabbitmq_client(f"consumer_{n}") for n in range(num_subs))
    mocked_message_parsers = [mocker.AsyncMock(return_value=True) for _ in range(num_subs)]

    publisher = create_rabbitmq_client("publisher")
    message = random_rabbit_message()
    exchange_name = random_exchange_name()
    await asyncio.gather(
        *(
            consumer.subscribe(exchange_name, parser)
            for consumer, parser in zip(consumers, mocked_message_parsers, strict=True)
        )
    )

    await publisher.publish(exchange_name, message)
    await asyncio.gather(*(_assert_message_received(parser, 1, message) for parser in mocked_message_parsers))


async def test_rabbit_client_pub_sub_republishes_if_exception_raised(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")

    message = random_rabbit_message()

    def _raise_once_then_true(*args, **kwargs):
        _raise_once_then_true.calls += 1

        if _raise_once_then_true.calls == 1:
            msg = "this is a test!"
            raise KeyError(msg)
        return _raise_once_then_true.calls != 2

    exchange_name = random_exchange_name()
    _raise_once_then_true.calls = 0
    mocked_message_parser.side_effect = _raise_once_then_true
    await consumer.subscribe(exchange_name, mocked_message_parser)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 3, message)


@pytest.fixture
async def ensure_queue_deletion(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
) -> AsyncIterator[Callable[[QueueName], None]]:
    created_queues = set()

    def _(queue_name: QueueName) -> None:
        created_queues.add(queue_name)

    yield _

    client = create_rabbitmq_client("ensure_queue_deletion")
    await asyncio.gather(*(client.unsubscribe(q) for q in created_queues))


@pytest.mark.parametrize("defined_queue_name", [None, "pytest-queue"])
@pytest.mark.parametrize("num_subs", [10])
async def test_pub_sub_with_non_exclusive_queue(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    num_subs: int,
    defined_queue_name: QueueName | None,
    ensure_queue_deletion: Callable[[QueueName], None],
):
    consumers = (create_rabbitmq_client(f"consumer_{n}") for n in range(num_subs))
    mocked_message_parsers = [mocker.AsyncMock(return_value=True) for _ in range(num_subs)]

    publisher = create_rabbitmq_client("publisher")
    message = random_rabbit_message()
    exchange_name = random_exchange_name()
    list_queue_name_consumer_mappings = await asyncio.gather(
        *(
            consumer.subscribe(
                exchange_name,
                parser,
                exclusive_queue=False,
                non_exclusive_queue_name=defined_queue_name,
            )
            for consumer, parser in zip(consumers, mocked_message_parsers, strict=True)
        )
    )
    for queue_name, _ in list_queue_name_consumer_mappings:
        assert queue_name == exchange_name if defined_queue_name is None else defined_queue_name
        ensure_queue_deletion(queue_name)
        ensure_queue_deletion(f"delayed_{queue_name}")
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
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")
    message = random_rabbit_message()

    exchange_name = random_exchange_name()
    asyncio.get_event_loop().run_until_complete(consumer.subscribe(exchange_name, mocked_message_parser))

    async def async_fct_to_test():
        await publisher.publish(exchange_name, message)
        await _assert_message_received(mocked_message_parser, 1, message)
        mocked_message_parser.reset_mock()

    def run_test_async():
        asyncio.get_event_loop().run_until_complete(async_fct_to_test())

    benchmark.pedantic(run_test_async, iterations=1, rounds=10)


async def test_rabbit_pub_sub_with_topic(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    exchange_name = f"{random_exchange_name()}_topic"
    critical_message = random_rabbit_message(topic="pytest.red.critical")
    debug_message = random_rabbit_message(topic="pytest.orange.debug")
    publisher = create_rabbitmq_client("publisher")

    all_receiving_consumer = create_rabbitmq_client("all_receiving_consumer")
    all_receiving_mocked_message_parser = mocker.AsyncMock(return_value=True)
    await all_receiving_consumer.subscribe(
        exchange_name, all_receiving_mocked_message_parser, topics=[BIND_TO_ALL_TOPICS]
    )

    only_critical_consumer = create_rabbitmq_client("only_critical_consumer")
    only_critical_mocked_message_parser = mocker.AsyncMock(return_value=True)
    await only_critical_consumer.subscribe(exchange_name, only_critical_mocked_message_parser, topics=["*.*.critical"])

    orange_and_critical_consumer = create_rabbitmq_client("orange_and_critical_consumer")
    orange_and_critical_mocked_message_parser = mocker.AsyncMock(return_value=True)
    await orange_and_critical_consumer.subscribe(
        exchange_name,
        orange_and_critical_mocked_message_parser,
        topics=["*.*.critical", "*.orange.*"],
    )

    # check now that topic is working
    await publisher.publish(exchange_name, critical_message)
    await publisher.publish(exchange_name, debug_message)

    await _assert_message_received(all_receiving_mocked_message_parser, 2, critical_message)
    await _assert_message_received(all_receiving_mocked_message_parser, 2, debug_message)
    await _assert_message_received(only_critical_mocked_message_parser, 1, critical_message)
    await _assert_message_received(orange_and_critical_mocked_message_parser, 2, critical_message)
    await _assert_message_received(orange_and_critical_mocked_message_parser, 2, debug_message)


async def test_rabbit_pub_sub_bind_and_unbind_topics(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    exchange_name = f"{random_exchange_name()}_topic"
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")
    severities = ["debug", "info", "warning", "critical"]
    messages = {sev: random_rabbit_message(topic=f"pytest.{sev}") for sev in severities}

    # send 1 message of each type
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages.values()))

    # we should get no messages since no one was subscribed
    queue_name, _ = await consumer.subscribe(exchange_name, mocked_message_parser, topics=[])
    await _assert_message_received(mocked_message_parser, 0)

    # now we should also not get anything since we are not interested in any topic
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages.values()))
    await _assert_message_received(mocked_message_parser, 0)

    # we are interested in warnings and critical
    await consumer.add_topics(exchange_name, topics=["*.warning", "*.critical"])
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages.values()))
    await _assert_message_received(mocked_message_parser, 2, messages["critical"])
    await _assert_message_received(mocked_message_parser, 2, messages["warning"])
    mocked_message_parser.reset_mock()
    # adding again the same topics makes no difference, we should still have 2 messages
    await consumer.add_topics(exchange_name, topics=["*.warning"])
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages.values()))
    await _assert_message_received(mocked_message_parser, 2, messages["critical"])
    await _assert_message_received(mocked_message_parser, 2, messages["warning"])
    mocked_message_parser.reset_mock()

    # after unsubscribing, we do not receive warnings anymore
    await consumer.remove_topics(exchange_name, topics=["*.warning"])
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages.values()))
    await _assert_message_received(mocked_message_parser, 1, messages["critical"])
    mocked_message_parser.reset_mock()

    # after unsubscribing something that does not exist, we still receive the same things
    await consumer.remove_topics(exchange_name, topics=[])
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages.values()))
    await _assert_message_received(mocked_message_parser, 1, messages["critical"])
    mocked_message_parser.reset_mock()

    # after unsubscribing we receive nothing anymore
    await consumer.unsubscribe(queue_name)
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages.values()))
    await _assert_message_received(mocked_message_parser, 0)


async def test_rabbit_adding_topics_to_a_fanout_exchange(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    exchange_name = f"{random_exchange_name()}_fanout"
    message = random_rabbit_message()
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")
    queue_name, _ = await consumer.subscribe(exchange_name, mocked_message_parser)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()
    # this changes nothing on a FANOUT exchange
    await consumer.add_topics(exchange_name, topics=["some_topics"])
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()
    # this changes nothing on a FANOUT exchange
    await consumer.remove_topics(exchange_name, topics=["some_topics"])
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 1, message)
    mocked_message_parser.reset_mock()
    # this will do something
    await consumer.unsubscribe(queue_name)
    await publisher.publish(exchange_name, message)
    await _assert_message_received(mocked_message_parser, 0)


@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors
async def test_rabbit_not_using_the_same_exchange_type_raises(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
):
    exchange_name = f"{random_exchange_name()}_fanout"
    client = create_rabbitmq_client("consumer")
    # this will create a FANOUT exchange
    await client.subscribe(exchange_name, mocked_message_parser)
    # now do a second subscription with topics, will create a TOPICS exchange
    with pytest.raises(aio_pika.exceptions.ChannelPreconditionFailed):
        await client.subscribe(exchange_name, mocked_message_parser, topics=[])


@pytest.mark.parametrize("idempotent_attempts", [10])
@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors
async def test_unsubscribe_consumer(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    idempotent_attempts: PositiveFloat,
):
    exchange_name = f"{random_exchange_name()}"
    client = create_rabbitmq_client("consumer")
    queue_name, consumer_tag = await client.subscribe(exchange_name, mocked_message_parser, exclusive_queue=False)

    # Unsubscribe just a consumer, the queue will be still there
    for _ in range(idempotent_attempts):
        await client.unsubscribe_consumer(queue_name, consumer_tag)

    # Unsubscribe the queue
    for _ in range(idempotent_attempts):
        await client.unsubscribe(queue_name)


async def _wait_until_stable(
    get_value: Callable[[], int], *, stable_polls: int = 3, poll_interval_s: float = 0.1, timeout_s: float = 5
) -> int:
    """Polls `get_value()` until it returns the same value `stable_polls` times in a row,
    then returns that value. Deterministic replacement for a fixed sleep when waiting for
    an asynchronous background process (e.g. draining a queue) to become quiescent."""
    deadline = asyncio.get_running_loop().time() + timeout_s
    last_value = get_value()
    stable_count = 1
    while stable_count < stable_polls:
        if asyncio.get_running_loop().time() > deadline:
            msg = f"value did not stabilize within {timeout_s}s (last seen: {last_value})"
            raise TimeoutError(msg)
        await asyncio.sleep(poll_interval_s)
        current_value = get_value()
        if current_value == last_value:
            stable_count += 1
        else:
            last_value = current_value
            stable_count = 1
    return last_value


async def _wait_until_queue_drained(
    connection_pool: aio_pika.pool.Pool, queue_name: QueueName, *, timeout_s: float = 5
) -> None:
    """Polls a queue's ready-message count via passive declare until it reaches zero, using a
    dedicated channel (not the client's shared channel pool, to avoid interleaving with active
    consumer traffic). Deterministic replacement for a fixed sleep before closing a connection.

    NOTE: not suitable for queues that ever hit `x-max-length` overflow (drop-head): RabbitMQ's
    reported `message_count` can remain permanently off-by-N after such truncation even though the
    queue is physically empty (confirmed independently via `basic.get`); for those, poll an
    application-level counter (e.g. the handler's own received-count) instead.
    """
    async with connection_pool.acquire() as connection:
        channel = await connection.channel()
        try:
            async for attempt in AsyncRetrying(
                wait=wait_fixed(0.05),
                stop=stop_after_delay(timeout_s),
                retry=retry_if_exception_type(AssertionError),
                reraise=True,
            ):
                with attempt:
                    declared = await channel.declare_queue(queue_name, passive=True)
                    assert declared.declaration_result.message_count == 0
        finally:
            await channel.close()


async def test_subscribe_with_max_length_drops_oldest_ready_messages(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")
    exchange_name = random_exchange_name()

    block_processing = asyncio.Event()
    received: list[bytes] = []

    async def _blocking_handler(data: bytes) -> bool:
        received.append(data)
        await block_processing.wait()
        return True

    max_length = 5
    queue_name, _ = await consumer.subscribe(
        exchange_name,
        _blocking_handler,
        prefetch_count=1,
        max_length=max_length,
        # NOTE: RabbitMQ dead-letters messages dropped by `x-max-length` overflow too (reason
        # "maxlen"), not just nacked/expired ones. Without this, dropped messages bounce forever
        # between this queue and its delay queue until RabbitMQ's own dead-letter-cycle detector
        # catches it - exactly why the two are always paired in production (see subscribe()'s docs)
        enable_dead_letter_requeue=False,
    )

    num_messages = max_length + 10
    messages = [random_rabbit_message() for _ in range(num_messages)]
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages))

    # the first message is delivered and blocks the (single-prefetch) consumer;
    # the rest pile up as ready messages, capped by max_length
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert len(received) == 1

    assert consumer._connection_pool  # noqa: SLF001
    # NOTE: uses a dedicated channel, not consumer._channel_pool, since that shared pool
    # could hand out the channel that is currently mid-delivery of the unacked message
    async with consumer._connection_pool.acquire() as connection:  # noqa: SLF001
        channel = await connection.channel()
        declared = await channel.declare_queue(queue_name, passive=True)
        assert declared.declaration_result.message_count is not None
        assert declared.declaration_result.message_count <= max_length
        await channel.close()

    block_processing.set()
    # NOTE: deliberately NOT using `_wait_until_queue_drained` here: RabbitMQ's reported
    # `message_count` can get permanently stuck above zero after `x-max-length`/drop-head
    # truncation, even though the queue is physically empty. Polling the handler's own
    # received-count is the reliable, deterministic ground truth for "processing finished".
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.05),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert len(received) == max_length + 1
    # only the unacked message plus at most max_length ready ones ever got delivered
    assert 1 <= len(received) <= max_length + 1
    assert len(received) < num_messages


async def test_subscribe_prefetch_count_limits_concurrent_deliveries(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")
    exchange_name = random_exchange_name()

    release_processing = asyncio.Event()
    in_flight = 0
    max_in_flight = 0

    async def _handler(_: bytes) -> bool:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await release_processing.wait()
        in_flight -= 1
        return True

    prefetch_count = 4
    queue_name, _consumer_tag = await consumer.subscribe(exchange_name, _handler, prefetch_count=prefetch_count)

    messages = [random_rabbit_message() for _ in range(prefetch_count * 3)]
    await asyncio.gather(*(publisher.publish(exchange_name, m) for m in messages))

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(5),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert max_in_flight == prefetch_count

    # give it a bit more time to ensure it never exceeds the configured prefetch
    await asyncio.sleep(0.5)
    assert max_in_flight == prefetch_count

    release_processing.set()
    # deterministically wait for the queue to drain (all messages acked) before closing
    assert consumer._connection_pool  # noqa: SLF001
    await _wait_until_queue_drained(consumer._connection_pool, queue_name)  # noqa: SLF001


async def test_subscribe_enable_dead_letter_requeue_false_drops_failed_messages(
    on_message_spy: mock.Mock,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")
    exchange_name = random_exchange_name()

    async def _always_fail(_: Any) -> bool:
        return False

    await consumer.subscribe(
        exchange_name,
        _always_fail,
        enable_dead_letter_requeue=False,
        unexpected_error_retry_delay_s=_ON_ERROR_DELAY_S,
    )
    message = random_rabbit_message()
    await publisher.publish(exchange_name, message)

    # with the retry machinery disabled, a failing message is delivered exactly once, never retried
    await _assert_wait_for_messages(on_message_spy, 1)


async def test_subscribe_backlog_monitor_warns_when_consumer_falls_behind(
    caplog: pytest.LogCaptureFixture,
    mocker: MockerFixture,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    mocker.patch.object(_client, "_BACKLOG_MONITOR_INTERVAL", datetime.timedelta(milliseconds=50))
    caplog.set_level(logging.WARNING)

    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")
    exchange_name = random_exchange_name()

    block_processing = asyncio.Event()
    processed_count = 0

    async def _blocking_handler(_: bytes) -> bool:
        nonlocal processed_count
        await block_processing.wait()
        processed_count += 1
        return True

    _queue_name, _consumer_tag = await consumer.subscribe(
        exchange_name,
        _blocking_handler,
        prefetch_count=1,
        max_length=10000,
    )

    # publish continuously, much faster than every backlog check, so that the (blocked)
    # consumer never drains anything and the ready count grows on every consecutive check
    stop_publishing = asyncio.Event()

    async def _publish_forever() -> None:
        while not stop_publishing.is_set():
            await publisher.publish(exchange_name, random_rabbit_message())

    publish_task = asyncio.create_task(_publish_forever())
    try:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.1),
            stop=stop_after_delay(5),
            retry=retry_if_exception_type(AssertionError),
            reraise=True,
        ):
            with attempt:
                assert "backlog kept growing" in caplog.text
    finally:
        stop_publishing.set()
        await publish_task
        block_processing.set()
        # NOTE: deliberately NOT using `_wait_until_queue_drained` here: this queue's
        # `max_length` overflow (drop-head) can leave RabbitMQ's reported `message_count`
        # permanently stuck above zero even once the queue is physically empty. Polling the
        # handler's own processed-count until it stops growing is the reliable, deterministic
        # way to know the consumer has caught up before closing the connection.
        await _wait_until_stable(lambda: processed_count, timeout_s=10)
