# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access


import json
import logging
import subprocess
import time
from threading import Thread
from typing import cast

import pytest
import socketio
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import WebSocket as PlaywrightWebSocket
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import RobustWebSocket

# FastAPI application setup
app = FastAPI()
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
sio_app = socketio.ASGIApp(sio)
app.mount("/", sio_app)


@sio.event
async def connect(sid, environ):
    print(f"Server: Client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"Server: Client disconnected: {sid}")


@sio.event
async def message(sid, data):
    print(f"Server: Message received: {data}")
    await sio.send(f"Echo: {data}")


@pytest.fixture(scope="module")
def fastapi_server():
    """Starts a FastAPI server in a separate thread."""
    server_thread = Thread(
        target=uvicorn.run,
        kwargs={
            "app": app,
            "host": "127.0.0.1",
            "port": 8000,
            "log_level": "info",
        },
        daemon=True,
    )
    server_thread.start()
    return "http://127.0.0.1:8000"
    # No explicit shutdown needed as the thread is daemonized


@pytest.fixture
def real_page() -> Page:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        yield page
        browser.close()


@pytest.fixture(scope="session")
def download_playwright_browser() -> None:
    subprocess.run(["playwright", "install", "chromium"], check=True)  # noqa: S607


def test_robust_websocket_with_socketio(download_playwright_browser: None, real_page: Page, fastapi_server: str):
    # Connect to the FastAPI server
    server_url = f"{fastapi_server}"
    real_page.goto(f"{fastapi_server}")  # Simulate visiting the server

    # Load the socket.io client library in the browser context
    real_page.evaluate(
        """
        const script = document.createElement('script');
        script.src = "https://cdn.socket.io/4.5.4/socket.io.min.js";
        script.onload = () => console.log("Socket.IO client library loaded");
        document.head.appendChild(script);
        """
    )

    # Wait for the socket.io library to be available
    real_page.wait_for_function("() => window.io !== undefined")

    # Establish a WebSocket connection using socket.io
    with real_page.expect_websocket() as ws_info:
        real_page.evaluate(
            f"""
            window.ws = io("{server_url}", {{ transports: ["websocket"] }});
            window.ws.on("connect", () => console.log("Connected to server"));
            window.ws.on("message", (data) => console.log("Message received:", data));
            """
        )  # Open WebSocket in the browser
        websocket: PlaywrightWebSocket = ws_info.value

        # Create a RobustWebSocket instance using the Playwright WebSocket
        robust_ws = RobustWebSocket(page=real_page, ws=websocket)

        # Test sending and receiving messages
        real_page.wait_for_function("() => window.ws && window.ws.connected === true")
        with robust_ws.expect_event("framereceived", timeout=5000) as frame_received_event:
            real_page.evaluate("window.ws.send('Hello')")  # Send a message via WebSocket
            raw_response = frame_received_event.value
            # Decode the socket.io message format
            assert raw_response.startswith("42"), "Invalid socket.io message format"
            decoded_message = json.loads(raw_response[2:])  # Remove "42" prefix
            assert decoded_message[0] == "message"
            response = decoded_message[1]
        assert response == "Echo: Hello"

        # Simulate a network issue by disabling and re-enabling the network
        with log_context(logging.INFO, msg="Simulating network issue") as ctx:
            ctx.logger.info("First network issue")
            real_page.context.set_offline(True)  # Disable network
            real_page.wait_for_timeout(12000)  # Wait for 2 seconds to simulate network downtime
            real_page.context.set_offline(False)  # Re-enable network
            real_page.wait_for_timeout(12000)  # Wait for 2 seconds to simulate network downtime

            ctx.logger.info("Second network issue")
            real_page.context.set_offline(True)  # Disable network
            real_page.wait_for_timeout(2000)  # Wait for 2 seconds to simulate network downtime
            real_page.context.set_offline(False)  # Re-enable network
            real_page.wait_for_timeout(2000)  # Wait for 2 seconds to simulate network downtime

        # Test sending and receiving messages after automatic reconnection
        real_page.wait_for_function("() => window.ws && window.ws.connected === true")
        with robust_ws.expect_event("framereceived", timeout=5000) as frame_received_event:
            real_page.evaluate("window.ws.send('Reconnected')")  # Send a message
            raw_response = frame_received_event.value
            # Decode the socket.io message format
            assert raw_response.startswith("42"), "Invalid socket.io message format"
            decoded_message = json.loads(raw_response[2:])  # Remove "42" prefix
            assert decoded_message[0] == "message"
            response = decoded_message[1]
        assert response == "Echo: Reconnected"

        assert robust_ws._num_reconnections == 2, "Expected 2 restarts due to network issues"  # noqa: SLF001


# --- Fast, deterministic unit tests for `RobustWebSocket.expect_event()` ---
#
# These do not need a real browser/network: they fake just enough of the
# `playwright.sync_api.WebSocket` surface (`.on()`/`.expect_event()`) to drive
# `RobustWebSocket`/`_ReconnectableEventWaiter` through the reconnect-recovery
# logic directly and quickly, going through the same public `expect_event()`
# entry point production code uses.


class _FakeEventInfo:
    """Mimics playwright's EventInfo: `.value` either returns or raises."""

    def __init__(self, *, value: object = None, error: BaseException | None = None) -> None:
        self._value = value
        self._error = error

    @property
    def value(self) -> object:
        if self._error is not None:
            raise self._error
        return self._value


class _FakeEventContextManager:
    def __init__(self, event_info: _FakeEventInfo) -> None:
        self._event_info = event_info

    def __enter__(self) -> _FakeEventInfo:
        return self._event_info


class _FakeWebSocket:
    """Mimics playwright.sync_api.WebSocket enough for `RobustWebSocket`."""

    def __init__(self, *event_infos: _FakeEventInfo) -> None:
        self._event_infos = list(event_infos)

    def on(self, *_args: object, **_kwargs: object) -> None:
        """no-op: RobustWebSocket registers framesent/framereceived/close/socketerror listeners here."""

    def expect_event(self, *_args: object, **_kwargs: object) -> _FakeEventContextManager:
        return _FakeEventContextManager(self._event_infos.pop(0))


def _make_robust_websocket(ws: _FakeWebSocket) -> RobustWebSocket:
    return RobustWebSocket(page=cast(Page, None), ws=cast(PlaywrightWebSocket, ws))


def test_reconnectable_event_waiter_resolves_without_reconnect():
    robust_ws = _make_robust_websocket(_FakeWebSocket(_FakeEventInfo(value="hello")))

    waiter = robust_ws.expect_event("framereceived", timeout=1000)

    assert waiter.value == "hello"


def test_reconnectable_event_waiter_survives_mid_wait_reconnect():
    """Regression test for the original bug: a wait registered before a websocket
    reconnect must keep waiting on the *new* socket instead of raising the stale
    `Error: Socket closed` from the connection it was originally bound to.
    """
    old_ws = _FakeWebSocket(_FakeEventInfo(error=PlaywrightError("Socket closed")))
    robust_ws = _make_robust_websocket(old_ws)

    waiter = robust_ws.expect_event("framereceived", timeout=30000)

    # simulate RobustWebSocket transparently reconnecting to a brand new socket
    # while our wait was still in flight
    robust_ws.ws = cast(PlaywrightWebSocket, _FakeWebSocket(_FakeEventInfo(value="resolved-after-reconnect")))

    assert waiter.value == "resolved-after-reconnect"


def test_reconnectable_event_waiter_reraises_when_no_reconnect_happened():
    """If the socket really is gone and no new one took its place, the error must
    still propagate instead of retrying forever."""
    robust_ws = _make_robust_websocket(_FakeWebSocket(_FakeEventInfo(error=PlaywrightError("Socket closed"))))

    waiter = robust_ws.expect_event("framereceived", timeout=1000)

    with pytest.raises(PlaywrightError, match="Socket closed"):
        _ = waiter.value


def test_reconnectable_event_waiter_reraises_unrelated_errors():
    robust_ws = _make_robust_websocket(_FakeWebSocket(_FakeEventInfo(error=PlaywrightError("boom"))))

    waiter = robust_ws.expect_event("framereceived", timeout=1000)

    with pytest.raises(PlaywrightError, match="boom"):
        _ = waiter.value


def test_reconnectable_event_waiter_raises_timeout_once_deadline_elapsed():
    """Regression test: Playwright treats `timeout=0` as 'disable timeout' (wait
    forever), so an already-expired deadline must raise a timeout instead of
    silently re-arming the wait with an unlimited one."""
    old_ws = _FakeWebSocket(_FakeEventInfo(error=PlaywrightError("Socket closed")))
    robust_ws = _make_robust_websocket(old_ws)

    waiter = robust_ws.expect_event("framereceived", timeout=1)

    # should never be consulted: the deadline will already be gone by the time we re-attach
    robust_ws.ws = cast(PlaywrightWebSocket, _FakeWebSocket())
    time.sleep(0.05)  # let the 1ms deadline elapse

    with pytest.raises(PlaywrightTimeoutError):
        _ = waiter.value
