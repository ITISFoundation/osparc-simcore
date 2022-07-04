# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Iterator, cast

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


@pytest.fixture
def server_url(get_unused_port: Callable[[], int]) -> Iterator[str]:
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

        yield url

        proc.terminate()
        print(
            f"server @{url} stdout",
            "-" * 10,
            "\n",
            proc.stdout.read().decode("utf-8"),
            "-" * 30,
        )


def test_cancel_on_disconnect(server_url: str):
    print()
    response = requests.get(f"{server_url}/example?wait=0", timeout=2)
    print(response.url, "->", response.text)
    response.raise_for_status()

    with pytest.raises(requests.exceptions.ReadTimeout):
        response = requests.get(f"{server_url}/example?wait=2", timeout=1)

    response = requests.get(f"{server_url}/example?wait=1", timeout=2)
    print(response.url, "->", response.text)
    response.raise_for_status()
