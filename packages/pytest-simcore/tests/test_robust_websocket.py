# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access


import json
import logging
import subprocess
from threading import Thread

import pytest
import socketio
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Page, sync_playwright
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


@pytest.fixture
def robust_ws(download_playwright_browser: None, real_page: Page, fastapi_server: str) -> RobustWebSocket:
    """Navigates to the test server, opens a socket.io websocket connection there,
    and wraps it in a connected `RobustWebSocket`."""
    server_url = fastapi_server
    real_page.goto(server_url)  # Simulate visiting the server

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

    _wait_for_connected(real_page)
    return RobustWebSocket(page=real_page, ws=websocket)


def _wait_for_connected(real_page: Page) -> None:
    real_page.wait_for_function("() => window.ws && window.ws.connected === true")


def _decode_socketio_message(raw_response: str) -> str:
    """Decodes a socket.io `message` event payload (wire format: `42["message", <payload>]`)."""
    assert raw_response.startswith("42"), "Invalid socket.io message format"
    decoded_message = json.loads(raw_response[2:])  # Remove "42" prefix
    assert decoded_message[0] == "message"
    return decoded_message[1]


def _simulate_network_blip(real_page: Page, *, offline_ms: int) -> None:
    real_page.context.set_offline(True)  # Disable network
    real_page.wait_for_timeout(offline_ms)
    real_page.context.set_offline(False)  # Re-enable network
    real_page.wait_for_timeout(offline_ms)


def test_robust_websocket_with_socketio(robust_ws: RobustWebSocket, real_page: Page):
    # Test sending and receiving messages
    with robust_ws.expect_event("framereceived", timeout=5000) as frame_received_event:
        real_page.evaluate("window.ws.send('Hello')")  # Send a message via WebSocket
        response = _decode_socketio_message(frame_received_event.value)
    assert response == "Echo: Hello"

    # Simulate a network issue by disabling and re-enabling the network
    with log_context(logging.INFO, msg="Simulating network issue") as ctx:
        ctx.logger.info("First network issue")
        _simulate_network_blip(real_page, offline_ms=12000)

        ctx.logger.info("Second network issue")
        _simulate_network_blip(real_page, offline_ms=2000)

    # Test sending and receiving messages after automatic reconnection
    _wait_for_connected(real_page)
    with robust_ws.expect_event("framereceived", timeout=5000) as frame_received_event:
        real_page.evaluate("window.ws.send('Reconnected')")  # Send a message
        response = _decode_socketio_message(frame_received_event.value)
    assert response == "Echo: Reconnected"

    assert robust_ws._num_reconnections == 2, "Expected 2 restarts due to network issues"  # noqa: SLF001


def test_robust_websocket_reconnects_while_wait_is_pending(robust_ws: RobustWebSocket, real_page: Page):
    """Regression test for the actual bug that was fixed: keep an `expect_event`
    wait *open* (in-flight) while the underlying websocket is closed and
    `RobustWebSocket` transparently reconnects, and only let the awaited frame
    arrive *after* reconnection completes. Before the fix, the pending wait
    stayed bound to the now-dead old socket and raised a stale
    `Error: Socket closed` as soon as the `with` block exited - even though a
    healthy new connection was already in place by then.
    """
    # Keep a wait open *across* the entire disconnect/reconnect cycle: the
    # message that satisfies it is only sent *after* reconnection, so this
    # wait genuinely spans the socket swap done by `RobustWebSocket`.
    with robust_ws.expect_event("framereceived", timeout=20000) as frame_received_event:
        with log_context(logging.INFO, msg="Simulating a reconnect while a wait is in-flight") as ctx:
            ctx.logger.info("Disconnecting network while the wait is still pending")
            _simulate_network_blip(real_page, offline_ms=2000)
            _wait_for_connected(real_page)

        ctx.logger.info("Sending message only after reconnection has completed")
        real_page.evaluate("window.ws.send('SurvivedMidWaitReconnect')")  # Send a message via WebSocket
        response = _decode_socketio_message(frame_received_event.value)
    assert response == "Echo: SurvivedMidWaitReconnect"

    assert robust_ws._num_reconnections >= 1, (  # noqa: SLF001
        "Expected at least one reconnection to have happened while the wait was in flight"
    )
