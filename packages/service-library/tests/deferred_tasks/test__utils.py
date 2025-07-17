# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import asyncio
import operator
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from unittest.mock import Mock

import pytest
from faststream.broker.wrapper.call import HandlerCallWrapper
from faststream.exceptions import NackMessage, RejectMessage
from faststream.rabbit import (
    ExchangeType,
    RabbitBroker,
    RabbitExchange,
    RabbitRouter,
    TestRabbitBroker,
)
from pydantic import NonNegativeInt
from servicelib.deferred_tasks._utils import stop_retry_for_unintended_errors
from settings_library.rabbit import RabbitSettings
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def rabbit_router() -> RabbitRouter:
    return RabbitRouter()


@pytest.fixture
def rabbit_broker(rabbit_service: RabbitSettings) -> RabbitBroker:
    return RabbitBroker(rabbit_service.dsn)


@pytest.fixture
async def get_test_broker(
    rabbit_broker: RabbitBroker, rabbit_router: RabbitRouter
) -> Callable[[], AbstractAsyncContextManager[RabbitBroker]]:
    @asynccontextmanager
    async def _() -> AsyncIterator[RabbitBroker]:
        rabbit_broker.include_router(rabbit_router)

        async with TestRabbitBroker(rabbit_broker, with_real=True) as test_broker:
            yield test_broker

    return _


@pytest.fixture
def rabbit_exchange() -> RabbitExchange:
    return RabbitExchange("test_exchange", durable=True, auto_delete=True)


async def _assert_call_count(
    handler: HandlerCallWrapper,
    *,
    expected_count: NonNegativeInt,
    operation: Callable = operator.eq
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.01),
        stop=stop_after_delay(5),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            assert handler.mock
            count = len(handler.mock.call_args_list)
            assert operation(count, expected_count)


async def test_handler_called_as_expected(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(queue="print_message_no_deco", exchange=rabbit_exchange)
    async def print_message_no_deco(some_value: int) -> None:
        print(some_value)

    @rabbit_broker.subscriber(queue="print_message_with_deco", exchange=rabbit_exchange)
    @stop_retry_for_unintended_errors
    async def print_message_with_deco(some_value: int) -> None:
        print(some_value)

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            24, queue="print_message_no_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(print_message_no_deco, expected_count=1)

        await test_broker.publish(
            42, queue="print_message_with_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(print_message_with_deco, expected_count=1)


async def test_handler_nacks_message(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(
        queue="nacked_message_no_deco", exchange=rabbit_exchange, retry=True
    )
    async def nacked_message_no_deco(msg: str) -> None:
        raise NackMessage

    @rabbit_broker.subscriber(
        queue="nacked_message_with_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def nacked_message_with_deco(msg: str) -> None:
        raise NackMessage

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            "", queue="nacked_message_no_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(
            nacked_message_no_deco, expected_count=10, operation=operator.gt
        )

        await test_broker.publish(
            "", queue="nacked_message_with_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(
            nacked_message_with_deco, expected_count=10, operation=operator.gt
        )


async def test_handler_rejects_message(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(
        queue="rejected_message_no_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def rejected_message_no_deco(msg: str) -> None:
        raise RejectMessage

    @rabbit_broker.subscriber(
        queue="rejected_message_with_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def rejected_message_with_deco(msg: str) -> None:
        raise RejectMessage

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            "", queue="rejected_message_no_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(rejected_message_no_deco, expected_count=1)

        await test_broker.publish(
            "", queue="rejected_message_with_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(rejected_message_with_deco, expected_count=1)


async def test_handler_unintended_error(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    @rabbit_broker.subscriber(
        queue="unintended_error_no_deco", exchange=rabbit_exchange, retry=True
    )
    async def unintended_error_no_deco(msg: str) -> None:
        msg = "this was an unexpected error"
        raise RuntimeError(msg)

    @rabbit_broker.subscriber(
        queue="unintended_error_with_deco", exchange=rabbit_exchange, retry=True
    )
    @stop_retry_for_unintended_errors
    async def unintended_error_with_deco(msg: str) -> None:
        msg = "this was an unexpected error"
        raise RuntimeError(msg)

    async with get_test_broker() as test_broker:
        await test_broker.publish(
            "", queue="unintended_error_no_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(
            unintended_error_no_deco, expected_count=10, operation=operator.gt
        )

        await test_broker.publish(
            "", queue="unintended_error_with_deco", exchange=rabbit_exchange
        )
        await _assert_call_count(unintended_error_with_deco, expected_count=1)


async def test_handler_parallelism(
    rabbit_broker: RabbitBroker,
    rabbit_exchange: RabbitExchange,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):
    done_mock = Mock()

    @rabbit_broker.subscriber(queue="sleeper", exchange=rabbit_exchange, retry=True)
    async def handler_sleeper(sleep_duration: float) -> None:
        await asyncio.sleep(sleep_duration)
        done_mock()

    async def _sleep_for(test_broker: RabbitBroker, *, duration: float) -> None:
        await test_broker.publish(duration, queue="sleeper", exchange=rabbit_exchange)

    async def _wait_for_calls(mock: Mock, *, expected_calls: int) -> None:
        async for attempt in AsyncRetrying(
            wait=wait_fixed(0.01),
            stop=stop_after_delay(5),
            reraise=True,
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt:
                assert len(mock.call_args_list) == expected_calls

    request_count = 100
    sleep_duration = 0.1
    async with get_test_broker() as test_broker:
        start_time = time.time()

        await asyncio.gather(
            *[
                _sleep_for(test_broker, duration=sleep_duration)
                for _ in range(request_count)
            ]
        )

        await _wait_for_calls(done_mock, expected_calls=request_count)

        elapsed = time.time() - start_time

        # ensure the run in parallel by checking that they finish in a fraction of th total duration
        assert elapsed <= (sleep_duration * request_count) * 0.15


async def test_fan_out_exchange_message_delivery(
    rabbit_broker: RabbitBroker,
    get_test_broker: Callable[[], AbstractAsyncContextManager[RabbitBroker]],
):

    handler_1_call_count = Mock()
    handler_2_call_count = Mock()

    fan_out_exchange = RabbitExchange(
        "test_fan_out_exchange",
        type=ExchangeType.FANOUT,
        durable=True,
        auto_delete=True,
    )

    @rabbit_broker.subscriber(queue="handler_1", exchange=fan_out_exchange, retry=True)
    async def handler_1(sleep_duration: float) -> None:
        assert sleep_duration == 0.1
        handler_1_call_count(sleep_duration)

    @rabbit_broker.subscriber(queue="handler_2", exchange=fan_out_exchange, retry=True)
    async def handler_2(sleep_duration: float) -> None:
        assert sleep_duration == 0.1
        handler_2_call_count(sleep_duration)

    async with get_test_broker() as test_broker:
        await test_broker.publish(0.1, exchange=fan_out_exchange)

        await asyncio.sleep(1)

    assert len(handler_1_call_count.call_args_list) == 1
    assert len(handler_2_call_count.call_args_list) == 1
