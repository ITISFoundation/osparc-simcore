# pylint: disable=protected-access
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=no-name-in-module

"""Chatbox usage limits — streaming path, tested at the HTTP seam.

Each completion costs $0.0025 at the default Blended Rate (2.5 USD/MTok, 1000 tokens),
so Window Quotas in these tests are in the fractions of a cent.
"""

import asyncio
import json
import time
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Any, NoReturn
from unittest.mock import AsyncMock, MagicMock

import anyio
import httpx
import pytest
import redis.asyncio as aioredis
import respx
from fastapi import FastAPI, status
from httpx import AsyncClient, BasicAuth
from servicelib.celery.task_manager import TaskManager
from simcore_service_api_server._meta import API_VTAG
from simcore_service_api_server._service_responses import (
    _make_metered_sse_relay,
    create_streaming_chat_response,
)
from simcore_service_api_server.api.dependencies.celery import get_task_manager
from simcore_service_api_server.clients.chatbox_usage import (
    _LEDGER_STREAM_KEY,
    get_chatbox_usage_ledger,
)
from simcore_service_api_server.core.settings import ApplicationSettings
from simcore_service_api_server.models.schemas.responses import CreateResponseRequest
from simcore_service_api_server.services_http.chatbot import ChatbotApi, ChatbotSession

# every test needs an empty Usage Ledger: fake Redis state is shared across tests
pytestmark = pytest.mark.usefixtures("fresh_usage_ledger")


@pytest.fixture
def app(app: FastAPI) -> Iterator[FastAPI]:
    """The streaming branch never uses the TaskManager, so bypass it."""
    app.dependency_overrides[get_task_manager] = lambda: MagicMock(spec=TaskManager)
    yield app
    app.dependency_overrides.pop(get_task_manager, None)


_REDIS_DOWN = "redis is down"


async def _post_stream(client: AsyncClient, auth: BasicAuth, body: dict[str, object]) -> httpx.Response:
    return await client.post(f"/{API_VTAG}/responses", auth=auth, json=body)


@pytest.mark.parametrize("app_environment", [{"WINDOW_SPEND_USD": 0.003}], indirect=True)
async def test_stream_within_window_quota_allowed(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - window quota $0.003, each completion costs $0.0025
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )

    # ACT
    response = await _post_stream(client, auth, usage_builders.make_stream_body())

    # ASSERT - allowed and relayed unchanged
    assert response.status_code == status.HTTP_200_OK

    # ASSERT - the aggregated usage reached the client in the streamed body
    assert '"usage"' in response.text

    # ASSERT - the Chatbox is asked to report usage on the final streamed chunk
    downstream_body = json.loads(mocked_chatbot_backend.calls[0].request.content)
    assert downstream_body["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize("app_environment", [{"WINDOW_SPEND_USD": 0.003}], indirect=True)
async def test_stream_window_quota_exhausted_returns_403_with_reset(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )

    # ACT - first completion succeeds and debits the window
    first = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert first.status_code == status.HTTP_200_OK

    # ACT - second completion cannot fit in the window
    second = await _post_stream(client, auth, usage_builders.make_stream_body())

    # ASSERT - non-retryable 403 naming the quota, the reset time, and support
    assert second.status_code == status.HTTP_403_FORBIDDEN
    body = second.json()
    errors = json.dumps(body["errors"])
    assert "chatbox_window_quota_exceeded" in errors
    assert "available again" in errors.lower()
    assert "support" in errors.lower()

    # ASSERT - structured fields agree with the prose and the header
    assert body["code"] == "chatbox_window_quota_exceeded"
    assert body["reset_at"] is not None
    parsed_reset = datetime.fromisoformat(body["reset_at"])
    assert parsed_reset.tzinfo is not None
    retry_after = second.headers.get("Retry-After")
    assert retry_after is not None
    assert 0 < int(retry_after) <= 5 * 3600
    # reset_at is the window expiry, so it must sit about a Retry-After away
    delta = (parsed_reset - datetime.now(UTC)).total_seconds()
    assert abs(delta - int(retry_after)) < 30


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 0.003, "WINDOW_LENGTH": "0:00:02"}],
    indirect=True,
)
async def test_stream_window_expiry_restores_access(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - tiny 2 s window; two completions would exceed it
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )
    first = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert first.status_code == status.HTTP_200_OK
    second = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert second.status_code == status.HTTP_403_FORBIDDEN

    # ACT - wait for the Usage Window to age out
    await asyncio.sleep(2.2)
    third = await _post_stream(client, auth, usage_builders.make_stream_body())

    # ASSERT - a fresh window starts and the completion is allowed again
    assert third.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "app_environment",
    [{"REQUESTS_PER_MINUTE": 2, "WINDOW_SPEND_USD": 10}],
    indirect=True,
)
async def test_stream_rate_limit_returns_429_with_retry_after(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - Rate Limit 2/min, generous Window Quota so only the rate layer trips
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(10, 10), headers={"content-type": "text/event-stream"}
    )

    # ACT - five sequential requests. A minute bucket may roll over at most once
    # during the test, so at most 2+2=4 can be allowed: at least one 429 is guaranteed
    results = [await _post_stream(client, auth, usage_builders.make_stream_body()) for _ in range(5)]
    codes = [r.status_code for r in results]

    # ASSERT - only 200/429, the first request is never denied, and the burst is capped
    assert set(codes) <= {status.HTTP_200_OK, status.HTTP_429_TOO_MANY_REQUESTS}
    assert codes[0] == status.HTTP_200_OK
    denied = [r for r in results if r.status_code == status.HTTP_429_TOO_MANY_REQUESTS]
    assert denied, f"Rate Limit never tripped: {codes}"

    # ASSERT - proper retryable 429 with Retry-After within the minute window
    assert 0 < int(denied[0].headers["Retry-After"]) <= 61
    body = denied[0].json()
    assert "chatbox_rate_limited" in json.dumps(body["errors"])
    # the structured fields must agree with the header and the prose
    assert body["code"] == "chatbox_rate_limited"
    assert body["retry_after_seconds"] == int(denied[0].headers["Retry-After"])
    assert body["reset_at"] is None


@pytest.mark.parametrize(
    "app_environment",
    [{"PROVIDER_BUDGET_USD": 0.003, "HARD_STOP_FRACTION": 0.8, "WINDOW_SPEND_USD": 10}],
    indirect=True,
)
async def test_global_budget_hard_stop_403(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    app: FastAPI,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - Provider Budget 0.003 USD with an 80 % hard stop (0.0024). Seed the cumulative platform
    # Spend past the threshold: the Global Budget Guard is one platform-wide counter, so
    # once crossed it stops every user regardless of their own (empty) Window Quota.
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )
    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None
    await ledger._client.redis.hset(usage_builders.global_key, "spend", "0.0025")  # noqa: SLF001

    # ACT
    response = await _post_stream(client, auth, usage_builders.make_stream_body())

    # ASSERT - platform budget exhausted: distinct code, not user-fault, no reset time,
    # and the Chatbox was never called
    assert response.status_code == status.HTTP_403_FORBIDDEN
    body = response.json()
    errors = json.dumps(body["errors"])
    assert "provider_budget_exhausted" in errors
    assert "not caused by your usage" in errors.lower()
    assert "Retry-After" not in response.headers
    assert body["code"] == "provider_budget_exhausted"
    assert body["retry_after_seconds"] is None
    assert body["reset_at"] is None
    assert len(mocked_chatbot_backend.calls) == 0


@pytest.mark.parametrize(
    "app_environment",
    [{"PROVIDER_BUDGET_USD": 0.003, "HARD_STOP_FRACTION": 0.8, "WINDOW_SPEND_USD": 10}],
    indirect=True,
)
async def test_global_budget_hard_stop_counts_in_flight_reservations(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    app: FastAPI,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - settled Spend is zero, but in-flight Reservations alone sit past the
    # hard stop (0.0024). The guard must treat committed Spend (actual + reservations)
    # as spent: bounding overshoot means in-flight completions count, not only debits.
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )
    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None
    await ledger._client.redis.hset(usage_builders.global_key, "reservations", "0.0025")  # noqa: SLF001

    # ACT
    response = await _post_stream(client, auth, usage_builders.make_stream_body())

    # ASSERT - denied on committed Spend, Chatbox untouched
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "provider_budget_exhausted" in json.dumps(response.json()["errors"])
    assert len(mocked_chatbot_backend.calls) == 0


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_stream_usage_reconciled_to_reported_tokens(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    read_ledger_state,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - window/global accounts start empty; fake Redis expires are swept lazily,
    # so only this test's Spend is visible in the state reads.
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )

    # ACT - one completion reporting exactly 1000 tokens
    response = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert response.status_code == status.HTTP_200_OK

    # ASSERT - the Reservation was fully refunded and Spend reconciled to the ACTUAL
    # usage: 1000 tokens at 2.5 USD/MTok = $0.0025
    state = await read_ledger_state()
    assert len(state["windows"]) == 1
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert window["spend"] == pytest.approx(0.0025)
    assert state["global"]["spend"] == pytest.approx(0.0025)
    assert state["global"]["requests"] == 1


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_stream_missing_usage_falls_back_to_estimate(
    client: AsyncClient,
    auth: BasicAuth,
    usage_builders,
    read_ledger_state,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - a streamed completion WITHOUT any usage chunk
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_without_usage(), headers={"content-type": "text/event-stream"}
    )

    # ACT - the request must NOT fail because usage is missing
    response = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert response.status_code == status.HTTP_200_OK

    # ASSERT - an estimated Spend (chars/4 tokens) was debited, not zero
    state = await read_ledger_state()
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert window["spend"] > 0


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 0.003, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_stream_concurrent_admission_bounded_by_reservations(
    client: AsyncClient,
    auth: BasicAuth,
    app: FastAPI,
    usage_builders,
    monkeypatch: pytest.MonkeyPatch,
):
    # ARRANGE - window $0.003; cold start => each Reservation covers the whole window.
    # Hold the upstream reply open so the first Admission's Reservation is still in
    # flight when the second one is evaluated: the second must be rejected (overshoot
    # bounded by Reservations, not by actual usage).
    release_upstream = asyncio.Event()

    async def _slow_stream(_request: httpx.Request) -> httpx.Response:
        await release_upstream.wait()
        return httpx.Response(
            200,
            content=usage_builders.make_sse_with_usage(400, 600),
            headers={"content-type": "text/event-stream"},
        )

    with respx.mock(base_url=usage_builders.chatbot_base_url, assert_all_mocked=False) as mock:
        mock.post("/v1/chat/completions").mock(side_effect=_slow_stream)

        ledger = get_chatbox_usage_ledger(app)
        assert ledger is not None
        redis = ledger._client.redis  # noqa: SLF001

        first_task = asyncio.create_task(_post_stream(client, auth, usage_builders.make_stream_body()))

        # wait until the first request's Reservation is in flight
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5
        while True:
            held = float(await redis.hget(usage_builders.global_key, "reservations") or 0)
            if held > 0:
                break
            assert loop.time() < deadline, "first Reservation never landed"
            await asyncio.sleep(0.02)

        # ACT - second request while the first is still in flight
        second = await _post_stream(client, auth, usage_builders.make_stream_body())

        # ASSERT
        assert second.status_code == status.HTTP_403_FORBIDDEN
        assert "chatbox_window_quota_exceeded" in json.dumps(second.json()["errors"])

        release_upstream.set()
        first = await first_task
        assert first.status_code == status.HTTP_200_OK


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_redis_down_window_quota_fails_closed(
    client: AsyncClient,
    auth: BasicAuth,
    app: FastAPI,
    usage_builders,
    mocked_chatbot_backend: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
):
    # ARRANGE - only the Window Quota's CAS pipeline is broken; the Rate Limit path
    # (plain commands) stays healthy and must count the request
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(10, 10), headers={"content-type": "text/event-stream"}
    )

    def _broken(*_args: object, **_kwargs: object) -> NoReturn:
        raise aioredis.ConnectionError(_REDIS_DOWN)

    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None
    monkeypatch.setattr(ledger._client.redis, "pipeline", _broken, raising=False)  # noqa: SLF001

    # ACT / ASSERT - the Window Quota fails CLOSED (503, retryable), never an uncounted pass
    response = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    body = response.json()
    assert "chatbox_usage_ledger_unavailable" in json.dumps(body["errors"])
    assert int(response.headers["Retry-After"]) >= 1
    assert body["code"] == "chatbox_usage_ledger_unavailable"
    assert body["retry_after_seconds"] == int(response.headers["Retry-After"])
    # a server-side rejection carries a support_id for tracing
    assert body["support_id"]

    # ASSERT - the Rate Limit still counted the request, and it never reached the Chatbox
    redis = ledger._client.redis  # noqa: SLF001
    rate_keys = [key async for key in redis.scan_iter(f"{usage_builders.rate_key_prefix}:*")]
    assert len(rate_keys) == 1
    assert int(rate_keys[0].split(":")[-1]) == pytest.approx(int(time.time() // 60), abs=1)
    assert await redis.get(rate_keys[0]) == "1"
    assert len(mocked_chatbot_backend.calls) == 0


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "PROVIDER_BUDGET_USD": 0.01, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_metrics_expose_spend_budget_fraction_and_failures(
    client: AsyncClient,
    auth: BasicAuth,
    app: FastAPI,
    usage_builders,
    mocked_chatbot_backend: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
):
    # ARRANGE
    def _sample_sum(metric: Any, **labels: str) -> float:
        for family in metric.collect():
            for sample in family.samples:
                if all(sample.labels.get(k) == v for k, v in labels.items()):
                    return sample.value
        return 0.0

    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )
    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None

    # ACT - one successful completion
    assert (await _post_stream(client, auth, usage_builders.make_stream_body())).status_code == status.HTTP_200_OK

    # ASSERT - Spend counters (per-product and platform-wide) and the budget-fraction
    # gauge reflect it (0.0025 USD of a 0.01 USD budget = 25 %)
    assert _sample_sum(ledger._metrics.spend_usd_total, product_name="osparc") == pytest.approx(0.0025)  # noqa: SLF001
    assert _sample_sum(ledger._metrics.spend_usd_global_total) == pytest.approx(0.0025)  # noqa: SLF001
    assert _sample_sum(ledger._metrics.provider_budget_fraction) == pytest.approx(0.25)  # noqa: SLF001

    # ACT - a ledger failure (fail-closed admission)
    def _broken(*_args: object, **_kwargs: object) -> NoReturn:
        raise aioredis.ConnectionError(_REDIS_DOWN)

    monkeypatch.setattr(ledger._client.redis, "pipeline", _broken, raising=False)  # noqa: SLF001
    broken = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert broken.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    # ASSERT - the failure is counted per stage
    assert _sample_sum(ledger._metrics.ledger_failures_total, stage="window_quota") == 1  # noqa: SLF001


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 10, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_redis_down_rate_limit_fails_open(
    client: AsyncClient,
    auth: BasicAuth,
    app: FastAPI,
    usage_builders,
    read_ledger_state,
    mocked_chatbot_backend: respx.MockRouter,
    monkeypatch: pytest.MonkeyPatch,
):
    # ARRANGE - the Rate Limit's Redis commands blow up; the spend layers stay healthy
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(10, 10), headers={"content-type": "text/event-stream"}
    )

    def _broken(*_args: object, **_kwargs: object) -> NoReturn:
        raise aioredis.ConnectionError(_REDIS_DOWN)

    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None
    monkeypatch.setattr(ledger._client.redis, "incr", _broken, raising=False)  # noqa: SLF001

    # ACT / ASSERT - the burst guard fails OPEN: the completion still goes through,
    # metered by the (healthy) Window Quota
    response = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert response.status_code == status.HTTP_200_OK
    assert len(mocked_chatbot_backend.calls) == 1

    # ASSERT - and it was correctly metered
    state = await read_ledger_state()
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert window["spend"] > 0


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 0.003, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_stream_usage_lands_in_ledger_entry_as_actual(
    client: AsyncClient,
    auth: BasicAuth,
    app: FastAPI,
    usage_builders,
    mocked_chatbot_backend: respx.MockRouter,
):
    # ARRANGE - one completion reporting exactly 1000 real tokens
    mocked_chatbot_backend.post("/v1/chat/completions").respond(
        200, content=usage_builders.make_sse_with_usage(400, 600), headers={"content-type": "text/event-stream"}
    )

    # ACT
    response = await _post_stream(client, auth, usage_builders.make_stream_body())
    assert response.status_code == status.HTTP_200_OK

    # ASSERT - the ledger stream entry carries the ACTUAL tokens, not an estimate
    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None
    redis = ledger._client.redis  # noqa: SLF001
    entries = await redis.xrange(_LEDGER_STREAM_KEY)
    assert len(entries) == 1
    fields = entries[0][1]
    assert fields["estimated"] == "0"
    assert fields["total_tokens"] == "1000"
    assert fields["prompt_tokens"] == "400"
    assert fields["completion_tokens"] == "600"


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 0.003, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_client_abort_bills_estimate_instead_of_refund(
    app: FastAPI,
    read_ledger_state,
):
    # The HTTP test transport cannot simulate a mid-stream client disconnect, so the
    # relay is driven directly with a fake upstream response and a request that
    # reports a disconnect after the first chunk.

    # ARRANGE - a real Reservation in flight, and a two-chunk stream where the
    # client drops before the second chunk is relayed
    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None
    reservation = await ledger.admit_and_reserve(user_id=1, product_name="osparc")

    first_event = b'data: {"id": "r", "choices": [{"index": 0, "delta": {"content": "hello world"}}]}\n\n'
    abandoned_event = b'data: {"id": "r", "choices": [{"index": 0, "delta": {"content": "more text"}}]}\n\n'

    response = MagicMock(spec=httpx.Response)

    async def _aiter_bytes() -> AsyncIterator[bytes]:
        yield first_event
        yield abandoned_event

    response.aiter_bytes = _aiter_bytes
    response.aclose = AsyncMock()

    request = MagicMock()
    request.is_disconnected = AsyncMock(side_effect=[False, True])

    input_chars = 100

    # ACT - drain the relay: it stops at the disconnect
    relayed = [
        chunk
        async for chunk in _make_metered_sse_relay(
            response=response,
            request=request,
            ledger=ledger,
            reservation=reservation,
            input_chars=input_chars,
        )
    ]
    assert relayed == [first_event]

    # ASSERT - the tokens streamed so far were billed as an estimate instead of the
    # Reservation being refunded: (100 + len("hello world")) // 4 = 27 tokens
    estimated_tokens = (input_chars + len("hello world")) // 4
    state = await read_ledger_state()
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert window["spend"] == pytest.approx(estimated_tokens / 1e6 * 2.5)

    # ASSERT - the ledger entry is flagged as estimated
    redis = ledger._client.redis  # noqa: SLF001
    entries = await redis.xrange(_LEDGER_STREAM_KEY)
    assert len(entries) == 1
    assert entries[0][1]["estimated"] == "1"
    assert entries[0][1]["total_tokens"] == f"{estimated_tokens}"


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 0.003, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_task_cancel_mid_stream_still_settles_reservation(
    app: FastAPI,
    read_ledger_state,
):
    # Starlette streams the relay inside an anyio task group and cancels it
    # level-triggered on client disconnect: an unshielded settlement await is
    # re-cancelled before its Redis write lands, leaking the Reservation here.

    # ARRANGE - a real Reservation and an upstream that never finishes streaming
    ledger = get_chatbox_usage_ledger(app)
    assert ledger is not None
    reservation = await ledger.admit_and_reserve(user_id=1, product_name="osparc")

    first_event = b'data: {"id": "r", "choices": [{"index": 0, "delta": {"content": "hello world"}}]}\n\n'
    stream_open = anyio.Event()

    response = MagicMock(spec=httpx.Response)

    async def _aiter_bytes() -> AsyncIterator[bytes]:
        yield first_event
        await stream_open.wait()  # the consumer never receives a second chunk

    response.aiter_bytes = _aiter_bytes
    response.aclose = AsyncMock()

    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=False)

    relayed: list[bytes] = []
    first_chunk_relayed = anyio.Event()

    async def _consume() -> None:
        async for chunk in _make_metered_sse_relay(
            response=response,
            request=request,
            ledger=ledger,
            reservation=reservation,
            input_chars=100,
        ):
            relayed.append(chunk)
            first_chunk_relayed.set()

    # ACT - cancel the consumer task mid-stream, as the response task group does
    # on disconnect, and let the shielded cleanup finish
    with anyio.move_on_after(10) as guard:
        async with anyio.create_task_group() as tg:
            tg.start_soon(_consume)
            await first_chunk_relayed.wait()
            tg.cancel_scope.cancel()
    assert not guard.cancelled_caught, "relay cleanup did not finish: settlement is not shielded"

    # ASSERT - the first chunk was relayed and billed as an estimate: (100 + len("hello world")) // 4 = 27 tokens
    assert relayed == [first_event]
    estimated_tokens = (100 + len("hello world")) // 4
    state = await read_ledger_state()
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert window["spend"] == pytest.approx(estimated_tokens / 1e6 * 2.5)

    # ASSERT - the upstream response was closed despite the cancellation
    response.aclose.assert_awaited_once()


@pytest.mark.parametrize(
    "app_environment",
    [{"WINDOW_SPEND_USD": 0.003, "REQUESTS_PER_MINUTE": 100}],
    indirect=True,
)
async def test_disconnect_while_opening_stream_refunds_reservation(
    app: FastAPI,
    read_ledger_state,
    usage_builders,
    mocker,
):
    # The metered relay only owns the Reservation from its creation onwards: a client
    # cancellation during the stream-open await (before the relay exists) must still
    # refund, or the cold-start Reservation locks the user out for the whole window.

    # ARRANGE - the client cancels (disconnect) while the upstream is still opening
    mocker.patch.object(ChatbotSession, "stream_chat_completion", side_effect=asyncio.CancelledError)

    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_CHATBOT is not None
    body = CreateResponseRequest.model_validate(usage_builders.make_stream_body())

    # ACT / ASSERT - the cancellation propagates unchanged
    with pytest.raises(asyncio.CancelledError):
        await create_streaming_chat_response(
            chatbot_settings=settings.API_SERVER_CHATBOT,
            chatbot_api=MagicMock(spec=ChatbotApi),
            body=body,
            request=MagicMock(),
            credential_hash="hash",
            user_id=1,
            product_name="osparc",
            ledger=get_chatbox_usage_ledger(app),
        )

    # ASSERT - the Reservation was refunded, nothing was spent
    state = await read_ledger_state()
    window = next(iter(state["windows"].values()))
    assert window["reservations"] == pytest.approx(0.0)
    assert "spend" not in window
