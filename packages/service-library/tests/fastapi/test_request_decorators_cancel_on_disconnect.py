# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Iterator, NamedTuple, cast

import pytest
import requests
from fastapi import FastAPI, Query, Request
from servicelib.fastapi.requests_decorators import cancel_on_disconnect

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# UTILS -------------------------

mock_app = FastAPI(title="Disconnect example")


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
        print("Exiting on cancellation")
        raise


# FIXTURES ---------------------


@pytest.fixture
def get_unused_port() -> Callable[[], int]:
    def go() -> int:
        """Return a port that is unused on the current host."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return cast(int, s.getsockname()[1])

    return go


class ServerInfo(NamedTuple):
    url: str
    proc: subprocess.Popen


@pytest.fixture
def server(get_unused_port: Callable[[], int]) -> Iterator[ServerInfo]:
    port = get_unused_port()
    with subprocess.Popen(
        [
            "uvicorn",
            "test_request_decorators_cancel_on_disconnect:mock_app",
            "--port",
            f"{port}",
        ],
        cwd=f"{CURRENT_DIR}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as proc:

        url = f"http://127.0.0.1:{port}"

        # some time to start
        time.sleep(2)

        # checks started successfully
        assert proc.stdout
        assert not proc.poll(), proc.stdout.read().decode("utf-8")

        yield ServerInfo(url, proc)

        proc.terminate()
        server_log = proc.stdout.read().decode("utf-8")
        print(
            f"server @{url} stdout",
            "-" * 10,
            "\n",
            server_log,
            "-" * 30,
        )

        assert "Exiting on cancellation" in server_log
        # server @http://127.0.0.1:44077 stdout ----------
        # Sleeping for 0.00
        # Sleep not cancelled
        # INFO:     127.0.0.1:35114 - "GET /example?wait=0 HTTP/1.1" 200 OK
        # Sleeping for 2.00
        # Exiting on cancellation
        # Sleeping for 1.00
        # Sleep not cancelled
        # INFO:     127.0.0.1:35134 - "GET /example?wait=1 HTTP/1.1" 200 OK


def test_cancel_on_disconnect(server: str):
    url, proc = server
    print()
    response = requests.get(f"{url}/example?wait=0", timeout=2)
    print(response.url, "->", response.text)
    response.raise_for_status()

    with pytest.raises(requests.exceptions.ReadTimeout):
        response = requests.get(f"{url}/example?wait=2", timeout=1)

    response = requests.get(f"{url}/example?wait=1", timeout=2)
    print(response.url, "->", response.text)
    response.raise_for_status()
