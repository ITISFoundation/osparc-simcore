# pylint: disable=redefined-outer-name

from contextlib import AsyncExitStack

import pytest
from pytest import FixtureRequest
from simcore_service_agent.modules.concurrency import (
    HandlerIsRunningError,
    HandlerUsageIsBlockedError,
    LowPriorityHandlerManager,
)

# UTILS


async def _handler_that_can_be_blocked(manager: LowPriorityHandlerManager) -> bool:
    """
    returns: True if it managed to run else False
    """
    try:
        async with manager.handler_barrier():
            return True
    except HandlerUsageIsBlockedError:
        return False


# FIXTURES


@pytest.fixture()
def manager() -> LowPriorityHandlerManager:
    return LowPriorityHandlerManager()


@pytest.fixture(params=[1, 2, 10])
def denying_handlers(request: FixtureRequest) -> int:
    return request.param


# TESTS


async def test_no_blocking_requests(manager: LowPriorityHandlerManager):
    assert await _handler_that_can_be_blocked(manager) is True


async def test_handler_is_already_running(manager: LowPriorityHandlerManager):
    async with manager.handler_barrier():
        with pytest.raises(HandlerIsRunningError):
            async with manager.deny_handler_usage():
                ...


async def test_blocked_by_other_calls_error(
    manager: LowPriorityHandlerManager, denying_handlers: int
):
    async with AsyncExitStack() as exit_stack:
        for _ in range(denying_handlers):
            await exit_stack.enter_async_context(manager.deny_handler_usage())

        with pytest.raises(
            HandlerUsageIsBlockedError, match=f"blocked by '{denying_handlers}' calls."
        ):
            async with manager.handler_barrier():
                ...


async def test_with_blocking_requests(
    manager: LowPriorityHandlerManager, denying_handlers: int
):
    async with AsyncExitStack() as exit_stack:

        # acquire enough resources that block
        for _ in range(denying_handlers):
            await exit_stack.enter_async_context(manager.deny_handler_usage())

        assert await _handler_that_can_be_blocked(manager) is False

    # once the resources are free it can be used again
    assert await _handler_that_can_be_blocked(manager) is True
