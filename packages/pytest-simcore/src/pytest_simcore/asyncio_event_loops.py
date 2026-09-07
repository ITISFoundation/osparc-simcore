"""
Our choice of plugin to test asyncio functionality is pytest-asyncio

Some other pytest plugins, e.g. pytest-aiohttp, define their own event loop
policies and event loops, which can conflict with pytest-asyncio.

This files unifies the event loop policy and event loop used by pytest-asyncio throughout
all the tests in this repository.

"""

import asyncio
from collections.abc import Callable

import pytest
import uvloop


def pytest_asyncio_loop_factories() -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    """Tell pytest-asyncio to build every test event loop with uvloop.

    This is the supported replacement for the (now deprecated) ``event_loop_policy``
    fixture override. Registering a single loop factory here makes all asyncio tests and
    their fixtures run on uvloop, the event loop we use in production.

    SEE https://pytest-asyncio.readthedocs.io/en/stable/how-to-guides/uvloop.html
    """
    return {"uvloop": uvloop.new_event_loop}


async def test_using_uvloop_event_loop():
    """Tests that `pytest_simcore.asyncio_event_loops` plugin is used and has an effect

    Manually import and add it your test-suite to run this test.
    """
    assert isinstance(asyncio.get_running_loop(), uvloop.Loop)


@pytest.fixture
async def loop() -> asyncio.AbstractEventLoop:
    """Override the event loop inside `aiohttp.pytest_plugin` with the one from `pytest-asyncio`.

    This provides the necessary fixtures to use pytest-asyncio with aiohttp!!!

    USAGE:

        pytest_plugins = [
            "aiohttp.pytest_plugin",  # No need to install pytest-aiohttp separately
        ]


    ERRORS:
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
