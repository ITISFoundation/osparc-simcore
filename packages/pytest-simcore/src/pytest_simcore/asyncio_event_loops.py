import asyncio

import pytest
import uvloop

pytest_plugins = [
    "aiohttp.pytest_plugin",  # No need to install pytest-aiohttp separately
]


@pytest.fixture(scope="session")
def event_loop_policy():
    """Override the event loop policy to use uvloop which is the one we use in production

    SEE https://pytest-asyncio.readthedocs.io/en/stable/how-to-guides/uvloop.html
    """
    return uvloop.EventLoopPolicy()


@pytest.fixture
async def loop() -> asyncio.AbstractEventLoop:
    """Override the event loop inside aiohttp.pytest_plugin with the one from pytest-asyncio.


        Otherwise error like this will be raised:

    >        if connector._loop is not loop:
    >           raise RuntimeError("Session and connector has to use same event loop")
    E           RuntimeError: Session and connector has to use same event loop

    .venv/lib/python3.11/site-packages/aiohttp/client.py:375: RuntimeError

    >        if connector._loop is not loop:
    >           raise RuntimeError("Session and connector has to use same event loop")
    >E           RuntimeError: Session and connector has to use same event loop

    .venv/lib/python3.11/site-packages/aiohttp/client.py:375: RuntimeError
    """
    return asyncio.get_running_loop()
