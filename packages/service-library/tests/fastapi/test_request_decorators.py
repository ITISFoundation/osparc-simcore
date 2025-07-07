# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NamedTuple
from unittest.mock import AsyncMock

import pytest
import requests
from fastapi import FastAPI, Query, Request
from servicelib.async_utils import TaskCancelCallback
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

POLLER_CLEANUP_DELAY_S = 100.0


CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent


mock_app = FastAPI(title="Disconnect example")

MESSAGE_ON_HANDLER_CANCELLATION = "Request was cancelled!!"


@mock_app.get("/example")
@cancel_on_disconnect
async def example(
    request: Request,
    wait: float = Query(..., description="Time to wait, in seconds"),
):
    try:
        print(f"Sleeping for {wait:.2f}")
        await asyncio.sleep(wait)
        print("Sleep not cancelled")
        return f"I waited for {wait:.2f}s and now this is the result"
    except asyncio.CancelledError:
        print(MESSAGE_ON_HANDLER_CANCELLATION)
        raise


class ServerInfo(NamedTuple):
    url: str
    proc: subprocess.Popen


@contextmanager
def server_lifetime(port: int) -> Iterator[ServerInfo]:
    with subprocess.Popen(
        [
            "uvicorn",
            f"{CURRENT_FILE.stem}:mock_app",
            "--port",
            f"{port}",
        ],
        cwd=f"{CURRENT_DIR}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:

        url = f"http://127.0.0.1:{port}"
        print("\nStarted", proc.args)

        # some time to start
        time.sleep(2)

        # checks started successfully
        assert proc.stdout
        assert not proc.poll(), proc.stdout.read().decode("utf-8")
        print("server is up and waiting for requests...")
        yield ServerInfo(url, proc)
        print("server is closing...")
        proc.terminate()
        print("server terminated")


def test_cancel_on_disconnect(get_unused_port: Callable[[], int]):

    with server_lifetime(port=get_unused_port()) as server:
        url, proc = server
        print("--> testing server")
        response = requests.get(f"{server.url}/example?wait=0", timeout=2)
        print(response.url, "->", response.text)
        response.raise_for_status()
        print("<-- server responds")

        print("--> testing server correctly cancels")
        with pytest.raises(requests.exceptions.ReadTimeout):
            response = requests.get(f"{server.url}/example?wait=2", timeout=0.5)
        print("<-- testing server correctly cancels done")

        print("--> testing server again")
        # NOTE: the timeout here appears to be sensitive. if it is set <5 the test hangs from time to time
        response = requests.get(f"{server.url}/example?wait=1", timeout=5)
        print(response.url, "->", response.text)
        response.raise_for_status()
        print("<-- testing server again done")

        # kill service
        server.proc.terminate()
        assert server.proc.stdout
        server_log = server.proc.stdout.read().decode("utf-8")
        print(
            f"{server.url=} stdout",
            "-" * 10,
            "\n",
            server_log,
            "-" * 30,
        )
        # server.url=http://127.0.0.1:44077 stdout ----------
        # Sleeping for 0.00
        # Sleep not cancelled
        # INFO:     127.0.0.1:35114 - "GET /example?wait=0 HTTP/1.1" 200 OK
        # Sleeping for 2.00
        # Exiting on cancellation
        # Sleeping for 1.00
        # Sleep not cancelled
        # INFO:     127.0.0.1:35134 - "GET /example?wait=1 HTTP/1.1" 200 OK

        assert MESSAGE_ON_HANDLER_CANCELLATION in server_log


@pytest.fixture
def long_running_poller_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[asyncio.Event, TaskCancelCallback, float], Awaitable]:

    async def _mock_disconnect_poller(
        close_event: asyncio.Event,
        cancel_awaitable: TaskCancelCallback,
        poll_interval: float,
    ):
        _mock_disconnect_poller.called = True
        while not await cancel_awaitable():
            await asyncio.sleep(2)
            if close_event.is_set():
                break

    monkeypatch.setattr(
        "servicelib.async_utils._poller_for_task_group",
        _mock_disconnect_poller,
    )
    return _mock_disconnect_poller


async def test_decorator_waits_for_poller_cleanup(
    long_running_poller_mock: Callable[
        [asyncio.Event, TaskCancelCallback, float], Awaitable
    ],
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
