# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock

import pytest
from fastapi import Request
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

POLLER_CLEANUP_DELAY_S = 100.0


@pytest.fixture
def long_running_poller_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[asyncio.Event, Request], Awaitable]:

    async def _mock_disconnect_poller(close_event: asyncio.Event, request: Request):
        _mock_disconnect_poller.called = True
        while not await request.is_disconnected():
            await asyncio.sleep(2)
            if close_event.is_set():
                break

    monkeypatch.setattr(
        "servicelib.fastapi.requests_decorators._disconnect_poller_for_task_group",
        _mock_disconnect_poller,
    )
    return _mock_disconnect_poller


async def test_decorator_waits_for_poller_cleanup(
    long_running_poller_mock: Callable[[asyncio.Event, Request], Awaitable],
):
    """
    Tests that the decorator's wrapper waits for the poller task to finish
    its cleanup, even if the handler finishes first, without needing a full server.
    """
    long_running_poller_mock.called = False
    handler_was_called = False

    @cancel_on_disconnect
    async def my_handler(request: Request):
        nonlocal handler_was_called
        handler_was_called = True
        await asyncio.sleep(0.1)  # Simulate quick work
        return "Success"

    # Mock a fastapi.Request object
    mock_request = AsyncMock(spec=Request)
    mock_request.is_disconnected.return_value = False

    # ---
    tasks_before = asyncio.all_tasks()

    # Call the decorated handler
    _ = await my_handler(mock_request)

    tasks_after = asyncio.all_tasks()
    # ---

    assert handler_was_called
    assert long_running_poller_mock.called == True

    # Check that no background tasks were left orphaned
    assert tasks_before == tasks_after
