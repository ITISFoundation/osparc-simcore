import json
import logging
from threading import Thread

import pytest
import socketio
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Page
from playwright.sync_api import WebSocket as PlaywrightWebSocket
from playwright.sync_api import sync_playwright
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
    yield "http://127.0.0.1:8000"
    # No explicit shutdown needed as the thread is daemonized


@pytest.fixture
def real_page() -> Page:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        yield page
        browser.close()


def test_robust_websocket_with_socketio(real_page: Page, fastapi_server: str):
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
        real_page.evaluate("window.ws.send('Hello')")  # Send a message via WebSocket
        with robust_ws.expect_event(
            "framereceived", timeout=5000
        ) as frame_received_event:
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
            real_page.wait_for_timeout(
                12000
            )  # Wait for 2 seconds to simulate network downtime
            real_page.context.set_offline(False)  # Re-enable network
            real_page.wait_for_timeout(
                12000
            )  # Wait for 2 seconds to simulate network downtime

            ctx.logger.info("Second network issue")
            real_page.context.set_offline(True)  # Disable network
            real_page.wait_for_timeout(
                2000
            )  # Wait for 2 seconds to simulate network downtime
            real_page.context.set_offline(False)  # Re-enable network
            real_page.wait_for_timeout(
                2000
            )  # Wait for 2 seconds to simulate network downtime

        # Test sending and receiving messages after automatic reconnection
        real_page.evaluate("window.ws.send('Reconnected')")  # Send a message
        with robust_ws.expect_event(
            "framereceived", timeout=5000
        ) as frame_received_event:
            raw_response = frame_received_event.value
            # Decode the socket.io message format
            assert raw_response.startswith("42"), "Invalid socket.io message format"
            decoded_message = json.loads(raw_response[2:])  # Remove "42" prefix
            assert decoded_message[0] == "message"
            response = decoded_message[1]
        assert response == "Echo: Reconnected"

        assert (
            robust_ws._num_reconnections == 2
        ), "Expected 2 restarts due to network issues"
