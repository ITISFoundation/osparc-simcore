# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access


import json
import logging
import subprocess
import typing
from threading import Thread

import pytest
import socketio
import uvicorn
from fastapi import FastAPI
from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import WebSocket as PlaywrightWebSocket
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.playwright import RobustWebSocket, decode_socketio_42_message

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


def _load_socketio_client(page: Page) -> None:
    """Loads the socket.io client library in the browser context of an already-navigated page."""
    page.evaluate(
        """
        const script = document.createElement('script');
        script.src = "https://cdn.socket.io/4.5.4/socket.io.min.js";
        script.onload = () => console.log("Socket.IO client library loaded");
        document.head.appendChild(script);
        """
    )
    page.wait_for_function("() => window.io !== undefined")


def _open_socketio_connection(
    page: Page,
    server_url: str,
    *,
    client_name: str = "ws",
    query: dict[str, str] | None = None,
) -> PlaywrightWebSocket:
    """Opens a new socket.io (websocket-only) connection from the page and captures its
    underlying `PlaywrightWebSocket`. `client_name` names the page-side socket.io client
    manager (`window[client_name]`) so several independent connections can coexist."""
    query_part = ""
    if query:
        query_part = ", query: " + json.dumps(query)
    with page.expect_websocket() as ws_info:
        page.evaluate(
            f"""
            window.{client_name} = io("{server_url}",
                {{ transports: ["websocket"]{query_part} }});
            window.{client_name}.on("connect", () => console.log("Connected to server"));
            window.{client_name}.on("message", (data) => console.log("Message received:", data));
            """
        )
        return ws_info.value


@pytest.fixture
def robust_ws(download_playwright_browser: None, real_page: Page, fastapi_server: str) -> RobustWebSocket:
    """Navigates to the test server, opens a socket.io websocket connection there,
    and wraps it in a connected `RobustWebSocket`."""
    real_page.goto(fastapi_server)  # Simulate visiting the server
    _load_socketio_client(real_page)
    websocket = _open_socketio_connection(real_page, fastapi_server)
    _wait_for_connected(real_page)
    return RobustWebSocket(page=real_page, ws=websocket)


def _wait_for_connected(real_page: Page) -> None:
    real_page.wait_for_function("() => window.ws && window.ws.connected === true")


def _take_socket_offline_and_wait_closed(page: Page, websocket: PlaywrightWebSocket) -> None:
    # NOTE: a websocket cannot be closed through playwright's API and an explicit client-side
    # manager close() would stop the socket.io automatic reconnections the tests rely on:
    # simulate a dead transport instead (like the connection refused during a cold start) and
    # wait until the page-side socket.io client notices it.
    page.context.set_offline(True)
    for _ in range(120):  # wait (max ~30s) until the client notices the dead transport
        if websocket.is_closed():
            return
        page.wait_for_timeout(250)
    pytest.fail("expected the websocket to be closed while offline")


def _decode_socketio_message(raw_response: str) -> str:
    event = decode_socketio_42_message(raw_response)
    assert event.name == "message"
    return typing.cast(str, event.obj)


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


def test_robust_websocket_reconnects_when_socket_closed_before_wrapping(
    download_playwright_browser: None, real_page: Page, fastapi_server: str
):
    """Regression test for `RobustWebSocket.__post_init__`: when the captured websocket has
    *already* failed its handshake (e.g. a socket.io connection refused during a service's
    cold start, like the deterministic 502 an nginx-fronted service answers while its backend
    port is not yet bound), its `socketerror`/`close` events are emitted before any listener
    can be attached, so the wrapper must detect `ws.is_closed()` and reconnect right away,
    without relying on those already-fired events.
    """
    real_page.goto(fastapi_server)
    _load_socketio_client(real_page)
    websocket = _open_socketio_connection(real_page, fastapi_server)
    _wait_for_connected(real_page)

    # take the socket down at the transport level so the page-side socket.io client
    # *automatically* retries once back online
    _take_socket_offline_and_wait_closed(real_page, websocket)

    # NOTE: back online the page-side client keeps retrying; the wrapper must adopt one of
    # those new connections during construction (the old socket's events are long gone)
    real_page.context.set_offline(False)
    robust_ws = RobustWebSocket(page=real_page, ws=websocket, reconnect_timeout=30000)

    assert not robust_ws.ws.is_closed(), "expected the wrapper to have replaced the closed socket"
    assert robust_ws.ws is not websocket
    assert robust_ws._num_reconnections == 1  # noqa: SLF001
    assert id(websocket) in robust_ws._reconnect_handled  # noqa: SLF001

    robust_ws.wait_until_connected(timeout=10000)
    _wait_for_connected(real_page)
    with robust_ws.expect_event("framereceived", timeout=5000) as frame_received_event:
        real_page.evaluate("window.ws.send('AfterColdStart')")
        response = _decode_socketio_message(frame_received_event.value)
    assert response == "Echo: AfterColdStart"

    robust_ws.auto_reconnect = False


def test_robust_websocket_reconnection_honors_ws_predicate(
    download_playwright_browser: None, real_page: Page, fastapi_server: str
):
    """Regression test for the `ws_predicate` filtering in `RobustWebSocket._attempt_reconnect`:
    candidate websockets rejected by the predicate (here: a socket.io client whose connection
    url does not carry the marker query parameter) must be skipped, and the wrapper must keep
    waiting for a *matching* new socket instead of adopting the first one that merely connects.
    """
    real_page.goto(fastapi_server)
    _load_socketio_client(real_page)
    websocket = _open_socketio_connection(real_page, fastapi_server)
    _wait_for_connected(real_page)

    # once the socket is back online below, a *plain* (non-matching) socket.io client reconnects
    # ~1s later and a *marker* (matching) one ~2.5s later: the wrapper built below must skip the
    # first candidate and adopt the second
    marker_query = {"osparc-test-marker": "robust"}

    _take_socket_offline_and_wait_closed(real_page, websocket)
    real_page.evaluate(
        f"""
        setTimeout(() => {{
            window.plainRetry = io("{fastapi_server}", {{ transports: ["websocket"] }});
        }}, 1000);
        setTimeout(() => {{
            window.markerClient = io("{fastapi_server}",
                {{ transports: ["websocket"], query: {json.dumps(marker_query)} }});
        }}, 2500);
        """
    )

    checked_urls: list[str] = []

    def _marker_only(candidate: PlaywrightWebSocket) -> bool:
        checked_urls.append(candidate.url)
        return "osparc-test-marker=robust" in candidate.url

    # NOTE: the socket is already closed here, so the wrapper reconnects during construction,
    # filtering every candidate through `ws_predicate` until the marker client connects
    real_page.context.set_offline(False)
    robust_ws = RobustWebSocket(page=real_page, ws=websocket, ws_predicate=_marker_only, reconnect_timeout=30000)

    assert any("osparc-test-marker=robust" not in url for url in checked_urls), (
        "expected the predicate to have rejected at least one non-matching reconnection"
    )
    assert "osparc-test-marker=robust" in robust_ws.ws.url
    assert robust_ws._num_reconnections == 1  # noqa: SLF001

    robust_ws.wait_until_connected(timeout=10000)
    robust_ws.auto_reconnect = False


def test_wait_until_connected_returns_immediately_on_already_established_socket(
    download_playwright_browser: None, real_page: Page, fastapi_server: str
):
    """Regression test for the initial-frame race: `page.expect_websocket` resolves when the
    browser *creates* the socket, so the socket.io 'open' frame can be delivered before
    `RobustWebSocket.__post_init__` attaches its `framereceived` listener. Here the race is
    forced deterministically: the socket is only wrapped *after* the page-side client reports
    `connected === true` (i.e. the open frame was definitely already received). Wrapping such
    an already-established healthy socket must mark it as connected right away: otherwise
    `wait_until_connected` spins until a *later* frame arrives (engine.io pings come only ~25s
    later) and spuriously times out a perfectly connected socket.
    """
    real_page.goto(fastapi_server)
    _load_socketio_client(real_page)
    with real_page.expect_websocket() as ws_info:
        real_page.evaluate(
            f"""
            window.ws = io("{fastapi_server}", {{ transports: ["websocket"] }});
            """
        )
        websocket = ws_info.value

    # the client is connected, i.e. it already received the socket.io 'open' frame -
    # this happens strictly *before* the wrapper attaches its listener below
    _wait_for_connected(real_page)

    robust_ws = RobustWebSocket(page=real_page, ws=websocket)
    assert robust_ws.ws is websocket
    assert not robust_ws.ws.is_closed()
    assert robust_ws._num_reconnections == 0  # noqa: SLF001

    # a healthy socket must be considered connected immediately, not after its *next* frame
    robust_ws.wait_until_connected(timeout=3000)

    robust_ws.auto_reconnect = False


def test_wait_until_connected_returns_after_socket_swap_and_times_out(robust_ws: RobustWebSocket, real_page: Page):
    """Regression test for `RobustWebSocket.wait_until_connected`: it must block (pumping the
    page's event loop so the event-driven reconnection can proceed) until the *new* socket has
    received its first frame, and must raise a `TimeoutError` when no connected socket appears
    within the timeout.
    """
    # positive: survive a network blip, then the blocking wait must return once the
    # reconnected socket is proven live by its first received frame
    _simulate_network_blip(real_page, offline_ms=2000)
    robust_ws.wait_until_connected(timeout=30000)
    assert robust_ws._num_reconnections >= 1  # noqa: SLF001

    # negative: forget the proof-of-life frames and give a tiny timeout: the wait must expire
    # (the current socket itself is healthy, so no reconnection will ever reset the deadline)
    robust_ws._frames_received_on.clear()  # noqa: SLF001
    robust_ws._num_reconnections = 0  # noqa: SLF001
    with pytest.raises(PlaywrightTimeoutError):
        robust_ws.wait_until_connected(timeout=500)


def test_robust_websocket_reconnects_when_wait_is_never_read_explicitly(robust_ws: RobustWebSocket, real_page: Page):
    """Regression test for `_ReconnectableEventWaiter.__exit__`: some callers (e.g.
    `expected_service_running`/`wait_for_service_running` in `playwright.py`, via
    `stack.enter_context(websocket.expect_event(...))`) never read `.value` themselves
    and instead rely on exiting the `with` block to perform the wait. If `__exit__`
    stops going through `.value` on a clean exit, this raises a stale
    `Error: Socket closed` instead of reattaching, even though this test never touches
    `.value`.
    """
    with robust_ws.expect_event("framereceived", timeout=20000):
        with log_context(logging.INFO, msg="Simulating a reconnect while a wait is in-flight") as ctx:
            ctx.logger.info("Disconnecting network while the wait is still pending")
            _simulate_network_blip(real_page, offline_ms=2000)
            _wait_for_connected(real_page)

        ctx.logger.info("Sending message only after reconnection has completed")
        real_page.evaluate("window.ws.send('SurvivedExitOnlyWait')")  # Send a message via WebSocket
        # NOTE: `.value` is deliberately never read here - exiting the `with` block below
        # must perform the wait (and reattach) on its own.

    assert robust_ws._num_reconnections >= 1, (  # noqa: SLF001
        "Expected at least one reconnection to have happened while the wait was in flight"
    )
