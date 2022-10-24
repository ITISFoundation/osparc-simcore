# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
from contextlib import suppress
from typing import AsyncIterator, Final

import pytest
from pydantic import PositiveFloat
from simcore_service_simcore_agent._app import Application
from simcore_service_simcore_agent.info._consumer import _async_request_info
from simcore_service_simcore_agent.info._provider import info_exposer

WAIF_FOR_SERVER_TO_START: Final[PositiveFloat] = 0.1


@pytest.fixture
async def provider() -> AsyncIterator[None]:
    app = Application()
    task = asyncio.create_task(info_exposer(app))

    await asyncio.sleep(WAIF_FOR_SERVER_TO_START)

    yield

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


async def test_ok(provider: None):
    result = await _async_request_info()
    print(result)

    assert result.startswith("Running tasks:")
    assert result.endswith("ALL OK")
