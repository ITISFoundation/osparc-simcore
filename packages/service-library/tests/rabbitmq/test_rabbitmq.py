# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=too-many-statements


import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final
from unittest import mock

import aio_pika
import pytest
from faker import Faker
from pytest_mock.plugin import MockerFixture
from servicelib.rabbitmq import BIND_TO_ALL_TOPICS, RabbitMQClient, _client
from servicelib.rabbitmq._client import DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS
from servicelib.rabbitmq._models import MessageHandler
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
                f"--> waiting for rabbitmq message [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )
            assert mocked_message_parser.call_count == expected_call_count
            if expected_call_count == 1:
                assert expected_message
                mocked_message_parser.assert_called_once_with(
                    expected_message.message.encode()
                )
            elif expected_call_count == 0:
                mocked_message_parser.assert_not_called()
            else:
                assert expected_message
                mocked_message_parser.assert_any_call(expected_message.message.encode())
            print(
                f"<-- rabbitmq message received after [{attempt.retry_state.attempt_number}, {attempt.retry_state.idle_for}]"
            )


async def test_rabbit_client_pub_sub_message_is_lost_if_no_consumer_present(
    cleanup_check_rabbitmq_server_has_no_errors: None,
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
    cleanup_check_rabbitmq_server_has_no_errors: None,
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
    cleanup_check_rabbitmq_server_has_no_errors: None,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    num_subs: int,
):
    consumers = (create_rabbitmq_client(f"consumer_{n}") for n in range(num_subs))
    mocked_message_parsers = [
        mocker.AsyncMock(return_value=True) for _ in range(num_subs)
    ]

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
    await asyncio.gather(
        *(
            _assert_message_received(parser, 1, message)
            for parser in mocked_message_parsers
        )
    )


async def test_rabbit_client_pub_sub_republishes_if_exception_raised(
    cleanup_check_rabbitmq_server_has_no_errors: None,
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
    cleanup_check_rabbitmq_server_has_no_errors: None,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocker: MockerFixture,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    num_subs: int,
):
    consumers = (create_rabbitmq_client(f"consumer_{n}") for n in range(num_subs))
    mocked_message_parsers = [
        mocker.AsyncMock(return_value=True) for _ in range(num_subs)
    ]

    publisher = create_rabbitmq_client("publisher")
    message = random_rabbit_message()
    exchange_name = random_exchange_name()
    await asyncio.gather(
        *(
            consumer.subscribe(exchange_name, parser, exclusive_queue=False)
            for consumer, parser in zip(consumers, mocked_message_parsers, strict=True)
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
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    consumer = create_rabbitmq_client("consumer")
    publisher = create_rabbitmq_client("publisher")
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
    cleanup_check_rabbitmq_server_has_no_errors: None,
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
    await only_critical_consumer.subscribe(
        exchange_name, only_critical_mocked_message_parser, topics=["*.*.critical"]
    )

    orange_and_critical_consumer = create_rabbitmq_client(
        "orange_and_critical_consumer"
    )
    orange_and_critical_mocked_message_parser = mocker.AsyncMock(return_value=True)
    await orange_and_critical_consumer.subscribe(
        exchange_name,
        orange_and_critical_mocked_message_parser,
        topics=["*.*.critical", "*.orange.*"],
    )

    # check now that topic is working
    await publisher.publish(exchange_name, critical_message)
    await publisher.publish(exchange_name, debug_message)

    await _assert_message_received(
        all_receiving_mocked_message_parser, 2, critical_message
    )
    await _assert_message_received(
        all_receiving_mocked_message_parser, 2, debug_message
    )
    await _assert_message_received(
        only_critical_mocked_message_parser, 1, critical_message
    )
    await _assert_message_received(
        orange_and_critical_mocked_message_parser, 2, critical_message
    )
    await _assert_message_received(
        orange_and_critical_mocked_message_parser, 2, debug_message
    )


async def test_rabbit_pub_sub_bind_and_unbind_topics(
    cleanup_check_rabbitmq_server_has_no_errors: None,
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
    await asyncio.gather(
        *(publisher.publish(exchange_name, m) for m in messages.values())
    )

    # we should get no messages since no one was subscribed
    queue_name = await consumer.subscribe(
        exchange_name, mocked_message_parser, topics=[]
    )
    await _assert_message_received(mocked_message_parser, 0)

    # now we should also not get anything since we are not interested in any topic
    await asyncio.gather(
        *(publisher.publish(exchange_name, m) for m in messages.values())
    )
    await _assert_message_received(mocked_message_parser, 0)

    # we are interested in warnings and critical
    await consumer.add_topics(exchange_name, topics=["*.warning", "*.critical"])
    await asyncio.gather(
        *(publisher.publish(exchange_name, m) for m in messages.values())
    )
    await _assert_message_received(mocked_message_parser, 2, messages["critical"])
    await _assert_message_received(mocked_message_parser, 2, messages["warning"])
    mocked_message_parser.reset_mock()
    # adding again the same topics makes no difference, we should still have 2 messages
    await consumer.add_topics(exchange_name, topics=["*.warning"])
    await asyncio.gather(
        *(publisher.publish(exchange_name, m) for m in messages.values())
    )
    await _assert_message_received(mocked_message_parser, 2, messages["critical"])
    await _assert_message_received(mocked_message_parser, 2, messages["warning"])
    mocked_message_parser.reset_mock()

    # after unsubscribing, we do not receive warnings anymore
    await consumer.remove_topics(exchange_name, topics=["*.warning"])
    await asyncio.gather(
        *(publisher.publish(exchange_name, m) for m in messages.values())
    )
    await _assert_message_received(mocked_message_parser, 1, messages["critical"])
    mocked_message_parser.reset_mock()

    # after unsubscribing something that does not exist, we still receive the same things
    await consumer.remove_topics(exchange_name, topics=[])
    await asyncio.gather(
        *(publisher.publish(exchange_name, m) for m in messages.values())
    )
    await _assert_message_received(mocked_message_parser, 1, messages["critical"])
    mocked_message_parser.reset_mock()

    # after unsubscribing we receive nothing anymore
    await consumer.unsubscribe(queue_name)
    await asyncio.gather(
        *(publisher.publish(exchange_name, m) for m in messages.values())
    )
    await _assert_message_received(mocked_message_parser, 0)


@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors()
async def test_rabbit_adding_topics_to_a_fanout_exchange(
    cleanup_check_rabbitmq_server_has_no_errors: None,
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
    random_rabbit_message: Callable[..., PytestRabbitMessage],
):
    exchange_name = f"{random_exchange_name()}_fanout"
    message = random_rabbit_message()
    publisher = create_rabbitmq_client("publisher")
    consumer = create_rabbitmq_client("consumer")
    queue_name = await consumer.subscribe(exchange_name, mocked_message_parser)
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


@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors()
async def test_rabbit_not_using_the_same_exchange_type_raises(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
):
    exchange_name = f"{random_exchange_name()}_fanout"
    client = create_rabbitmq_client("consumer")
    # this will create a FANOUT exchange
    await client.subscribe(exchange_name, mocked_message_parser)
    # now do a second subscribtion wiht topics, will create a TOPICS exchange
    with pytest.raises(aio_pika.exceptions.ChannelPreconditionFailed):
        await client.subscribe(exchange_name, mocked_message_parser, topics=[])


@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors()
async def test_unsubscribe_consumer(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    mocked_message_parser: mock.AsyncMock,
):
    exchange_name = f"{random_exchange_name()}"
    client = create_rabbitmq_client("consumer")
    await client.subscribe(exchange_name, mocked_message_parser, exclusive_queue=False)
    # Unsubsribe just a consumer, the queue will be still there
    await client.unsubscribe_consumer(exchange_name)
    # Unsubsribe the queue
    await client.unsubscribe(exchange_name)
    with pytest.raises(aio_pika.exceptions.ChannelNotFoundEntity):
        await client.unsubscribe(exchange_name)


@pytest.fixture
def on_message_spy(mocker: MockerFixture) -> mock.Mock:
    spy = mock.Mock()

    original_handler = _client._on_message  # noqa: SLF001

    async def __on_message(
        message_handler: MessageHandler,
        max_retries_upon_error: int,
        message: aio_pika.abc.AbstractIncomingMessage,
    ) -> None:
        await original_handler(message_handler, max_retries_upon_error, message)
        spy(message)

    mocker.patch(
        "servicelib.rabbitmq._client._on_message",
        side_effect=__on_message,
    )
    return spy


def _get_spy_report(mock: mock.Mock) -> dict[str, set[int]]:
    print(mock.call_args_list)

    results: dict[str, set[int]] = {}

    for entry in mock.call_args_list:
        message: aio_pika.abc.AbstractIncomingMessage = entry.args[0]
        assert message.routing_key is not None

        if message.routing_key not in results:
            results[message.routing_key] = set()

        count = _client._get_x_death_count(message)  # noqa: SLF001
        results[message.routing_key].add(count)

    return results


_ON_ERROR_DELAY_S: Final[float] = 0.1


async def _setup_publisher_and_subscriber(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    max_requeue_retry: int,
    topics: list[str] | None,
    message_handler: Callable[[Any], Awaitable[bool]],
) -> int:
    exchange_name = f"{random_exchange_name()}"
    client = create_rabbitmq_client("consumer")

    await client.subscribe(
        exchange_name,
        message_handler,
        topics=topics,
        exclusive_queue=False,
        unexpected_error_max_attempts=max_requeue_retry,
        unexpected_error_retry_delay_s=_ON_ERROR_DELAY_S,
    )

    publisher = create_rabbitmq_client("publisher")
    if topics is not None:
        for topic in topics:
            message = random_rabbit_message(topic=topic)
            await publisher.publish(exchange_name, message)
    else:
        message = random_rabbit_message()
        await publisher.publish(exchange_name, message)

    return 1 if topics is None else len(topics)


async def _assert_wait_for_messages(
    on_message_spy: mock.Mock, expected_results: int
) -> None:
    def _ensure_expected_calls() -> None:
        assert len(on_message_spy.call_args_list) == expected_results

    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(expected_results * _ON_ERROR_DELAY_S * 2),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            _ensure_expected_calls()

    # wait some more time to make sure retry mechanism did not trigger
    await asyncio.sleep(_ON_ERROR_DELAY_S * 3)
    _ensure_expected_calls()


_TOPICS: Final[list[list[str] | None]] = [
    None,
    ["one"],
    ["one", "two"],
]


@pytest.mark.parametrize("max_requeue_retry", [0, 1, 3, 10])
@pytest.mark.parametrize("topics", _TOPICS)
@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors()
async def test_subscribe_to_failing_message_handler(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    on_message_spy: mock.Mock,
    max_requeue_retry: int,
    topics: list[str] | None,
):
    async def _faulty_message_handler(message: Any) -> bool:
        msg = f"Always fail. Received message {message}"
        raise RuntimeError(msg)

    topics_multiplier = await _setup_publisher_and_subscriber(
        create_rabbitmq_client,
        random_exchange_name,
        random_rabbit_message,
        max_requeue_retry,
        topics,
        _faulty_message_handler,
    )

    expected_results = (max_requeue_retry + 1) * topics_multiplier
    await _assert_wait_for_messages(on_message_spy, expected_results)

    report = _get_spy_report(on_message_spy)
    routing_keys: list[str] = [""] if topics is None else topics
    assert report == {k: set(range(max_requeue_retry + 1)) for k in routing_keys}


@pytest.mark.parametrize("topics", _TOPICS)
@pytest.mark.no_cleanup_check_rabbitmq_server_has_no_errors()
async def test_subscribe_no_dead_letter_exchange_messages(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    random_exchange_name: Callable[[], str],
    random_rabbit_message: Callable[..., PytestRabbitMessage],
    on_message_spy: mock.Mock,
    topics: list[str] | None,
):
    message_failed: dict[str, bool] = {}

    async def _fail_once_then_succeed(message: Any) -> bool:
        print("Handling message", message)
        if message not in message_failed:
            message_failed[message] = False
        if not message_failed[message]:
            message_failed[message] = True
            return False
        return True

    topics_multiplier = await _setup_publisher_and_subscriber(
        create_rabbitmq_client,
        random_exchange_name,
        random_rabbit_message,
        DEFAULT_UNEXPECTED_ERROR_MAX_ATTEMPTS,
        topics,
        _fail_once_then_succeed,
    )

    expected_results = 2 * topics_multiplier
    await _assert_wait_for_messages(on_message_spy, expected_results)

    report = _get_spy_report(on_message_spy)
    routing_keys: list[str] = [""] if topics is None else topics
    assert report == {k: set(range(1)) for k in routing_keys}

    # ensure no headers in received messages, meaning the handler did not fail
    for entry in on_message_spy.call_args_list:
        assert entry.args[0].headers == {}
