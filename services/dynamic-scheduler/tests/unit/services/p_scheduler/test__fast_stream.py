# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import logging
from collections.abc import AsyncIterable, Callable, Iterable
from typing import Any

import pytest
from settings_library.rabbit import RabbitSettings
from simcore_service_dynamic_scheduler.services.p_scheduler._fast_stream import (
    FastStreamManager,
    MessageHandlerProtocol,
    RoutingKey,
)
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def router_keys() -> list[RoutingKey]:
    return ["rk1", "rk2", "rk3"]


@pytest.fixture
def message_tracker() -> Iterable[dict[RoutingKey, list[Any]]]:
    tracked = {}
    yield tracked
    tracked.clear()
    assert tracked == {}


@pytest.fixture
async def recording_handler(
    message_tracker: dict[RoutingKey, list[Any]],
) -> Callable[[RoutingKey], MessageHandlerProtocol]:
    def _(routing_key: RoutingKey) -> MessageHandlerProtocol:
        async def _handler(message: Any) -> None:
            print(f"💬 received on {routing_key=}: {message=}")
            if routing_key not in message_tracker:
                message_tracker[routing_key] = []
            message_tracker[routing_key].append(message)

        return _handler

    return _


@pytest.fixture
async def fast_stream_manager(
    rabbit_settings: RabbitSettings,
    recording_handler: Callable[[RoutingKey], MessageHandlerProtocol],
    router_keys: list[RoutingKey],
) -> AsyncIterable[FastStreamManager]:
    handlers: dict[RoutingKey, MessageHandlerProtocol] = {
        router_key: recording_handler(router_key) for router_key in router_keys
    }

    manager = FastStreamManager(rabbit_settings, handlers, log_level=logging.WARNING)
    await manager.setup()
    yield manager
    await manager.shutdown()


@pytest.fixture
def messages() -> list[Any]:
    return ["a_string", ["mixed", 3.14, "list"], 12, 12.34, {"key": "value"}]


async def test__fast_stream_manager_workflow(
    fast_stream_manager: FastStreamManager,
    router_keys: list[RoutingKey],
    message_tracker: dict[RoutingKey, list[Any]],
    messages: list[Any],
) -> None:
    for routing_key in router_keys:
        for message in messages:
            await fast_stream_manager.publish(message, routing_key)

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(2), wait=wait_fixed(0.1), retry=retry_if_exception_type(AssertionError)
    ):
        with attempt:
            await asyncio.sleep(0)  # yield to the event loop
            for routing_key in router_keys:
                assert message_tracker[routing_key] == messages
