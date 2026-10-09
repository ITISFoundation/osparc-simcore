"""Business logic for the `/responses` routes (Controller-Service-Repository split).

Both paths enforce the Chatbox limits: the Rate Limit first (fail-open), then the Window
Quota and Global Budget Guard place a Reservation (fail-closed). The streaming path
reconciles that Reservation against the usage reported by the Chatbox; the background
path hands it over to the worker, which reconciles at task end.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

import anyio
import httpx
from celery_library.async_jobs import submit_job
from common_library.json_serialization import json_loads
from fastapi import Request
from models_library.api_server.celery import API_SERVER_CELERY_QUEUE_DEFAULT
from models_library.celery import TaskExecutionMetadata
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import ValidationError
from servicelib.celery.task_manager import TaskManager
from servicelib.status_codes_utils import is_4xx_client_error
from starlette.responses import JSONResponse

from .clients.chatbox_usage import ChatboxUsageLedger, Reservation, UsageRecord
from .core.settings import ChatbotSettings
from .exceptions.backend_errors import ChatbotRequestError
from .exceptions.handlers._utils import create_error_json_response
from .exceptions.handlers._validation_errors import http422_error_handler
from .models.basic_types import SseStreamingResponse
from .models.domain.celery_models import ApiServerOwnerMetadata
from .models.domain.chatbot import DEFAULT_TOP_P
from .models.schemas.responses import (
    CreateResponseRequest,
    ResponseObject,
    ResponseStatus,
)
from .services_http.chatbot import ChatbotApi, ChatbotSession

_logger = logging.getLogger(__name__)

_TASK_NAME = "run_chat_completion"


async def _admit_and_reserve(
    ledger: ChatboxUsageLedger | None,
    *,
    credentials_hash: str,
    user_id: UserID,
    product_name: ProductName,
) -> Reservation | None:
    """Applies the Rate Limit (fail-open) and places a Reservation for the Window Quota
    and Global Budget Guard (fail-closed). Returns None when limits are not enforced.

    Raises:
        ChatboxRateLimitedError: the API key is over its per-minute request rate.
        ProviderBudgetExhaustedError: the Global Budget Guard hard stop is hit.
        ChatboxWindowQuotaExceededError: the Reservation does not fit the Window Quota.
        UsageLedgerUnavailableError: Redis cannot be trusted (fail-closed).
    """
    if ledger is None:
        return None

    await ledger.acquire_rate_limit(user_id=user_id, credentials_hash=credentials_hash)
    return await ledger.admit_and_reserve(user_id=user_id, product_name=product_name)


async def _release_reservation(
    ledger: ChatboxUsageLedger | None,
    reservation: Reservation | None,
    *,
    reason: str,
) -> None:
    if ledger is not None and reservation is not None:
        # callers here are error/cancellation paths: inside a level-triggered cancel
        # scope (client disconnect) an unshielded refund await is re-cancelled at its
        # first checkpoint, silently losing the Refund and leaking the Reservation
        # against the Window Quota until the whole Usage Window expires
        with anyio.CancelScope(shield=True):
            await ledger.release(reservation, reason=reason)


async def _relay_sse_response(response: httpx.Response, request: Request) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes():
            if await request.is_disconnected():
                break
            yield chunk
    finally:
        await response.aclose()


def _relay_downstream_client_error(response: httpx.Response) -> JSONResponse:
    """The chatbot service already validated the request and returned a client-facing
    error body (e.g. FastAPI's `{"detail": [...]}`) -- relay it as-is, with the same
    status code, instead of masking it behind a generic backend error."""
    try:
        payload = response.json()
        errors = payload.get("detail", response.text) if isinstance(payload, dict) else payload
    except ValueError:
        errors = response.text
    if not isinstance(errors, list):
        errors = [errors]
    return create_error_json_response(*errors, status_code=response.status_code)


def _extract_usage(payload: dict[str, Any]) -> UsageRecord | None:
    """The OpenAI-style aggregated `usage` object (sent on the final chunk, requested
    via stream_options), or None when the payload carries none."""
    if not isinstance(usage_obj := payload.get("usage"), dict):
        return None
    if not isinstance(usage_obj.get("total_tokens"), int):
        return None
    return UsageRecord(
        total_tokens=usage_obj["total_tokens"],
        prompt_tokens=usage_obj.get("prompt_tokens"),
        completion_tokens=usage_obj.get("completion_tokens"),
    )


def _count_delta_chars(payload: dict[str, Any]) -> int:
    """Length of the assistant text streamed by one payload's choice deltas."""
    text_chars = 0
    for choice in payload.get("choices") or []:
        if (
            isinstance(choice, dict)
            and isinstance(choice.get("delta"), dict)
            and isinstance(content := choice["delta"].get("content"), str)
        ):
            text_chars += len(content)
    return text_chars


def _parse_sse_event(raw_event: bytes) -> tuple[UsageRecord | None, int]:
    """Extracts the usage and the assistant text length from one SSE event."""
    usage: UsageRecord | None = None
    text_chars = 0
    for raw_line in raw_event.split(b"\n"):
        line = raw_line.strip()
        if not line.startswith(b"data:"):
            continue
        payload_bytes = line[len(b"data:") :].strip()
        try:
            payload = json_loads(payload_bytes)
        except ValueError:
            continue
        if not isinstance(payload, dict):
            continue
        usage = _extract_usage(payload) or usage
        text_chars += _count_delta_chars(payload)
    return usage, text_chars


class _SseUsageAccumulator:
    """Accumulates usage and output length across the SSE events of a stream.

    Network chunks can split an SSE event: the tail is kept until its terminator."""

    def __init__(self) -> None:
        self.usage: UsageRecord | None = None
        self.output_chars: int = 0
        self._buffer: bytes = b""

    def feed(self, chunk: bytes) -> None:
        self._buffer += chunk
        *complete_events, self._buffer = self._buffer.split(b"\n\n")
        for raw_event in complete_events:
            self._consume(raw_event)

    def close(self) -> None:
        # stream ended normally: parse the trailing bytes as the last event
        if self._buffer:
            self._consume(self._buffer)
            self._buffer = b""

    def _consume(self, raw_event: bytes) -> None:
        event_usage, text_chars = _parse_sse_event(raw_event)
        self.usage = event_usage or self.usage
        self.output_chars += text_chars


async def _settle_reservation(
    ledger: ChatboxUsageLedger,
    reservation: Reservation,
    *,
    failed: bool,
    completed: bool,
    usage: UsageRecord | None,
    input_chars: int,
    output_chars: int,
) -> None:
    if failed:
        await ledger.release(reservation, reason="stream_error")
    elif not completed:
        # client disconnected before the completion finished: the tokens streamed so far
        # were really burned upstream, so bill an estimate instead of refunding the whole
        # Reservation (a refund would let a client abort repeatedly to consume for free)
        await ledger.reconcile(
            reservation,
            UsageRecord.estimated_from_text(input_chars=input_chars, output_chars=output_chars),
        )
    else:
        # the Chatbox is expected to always report usage; if it did not, estimate from text
        # length and never fail the request over accounting
        await ledger.reconcile(
            reservation,
            usage or UsageRecord.estimated_from_text(input_chars=input_chars, output_chars=output_chars),
        )


def _make_metered_sse_relay(
    *,
    response: httpx.Response,
    request: Request,
    ledger: ChatboxUsageLedger,
    reservation: Reservation,
    input_chars: int,
) -> AsyncIterator[bytes]:
    async def _relay() -> AsyncIterator[bytes]:
        accumulator = _SseUsageAccumulator()
        completed = False
        failed = False
        try:
            async for chunk in response.aiter_bytes():
                if await request.is_disconnected():
                    break
                accumulator.feed(chunk)
                yield chunk
            else:
                accumulator.close()
                completed = True
        except (anyio.get_cancelled_exc_class(), GeneratorExit):
            # the consumer side went away mid-stream: a client disconnect reaches the
            # generator as task cancellation at the `yield` or as aclose() -> GeneratorExit
            raise
        except BaseException:
            # timeout / upstream abort mid-stream: refund the Reservation (the
            # released-reservations counter makes the uncounted burn visible)
            failed = True
            raise
        finally:
            # Starlette tears the stream down with a *level-triggered* cancel scope when
            # the client disconnects: an unshielded cleanup await is re-cancelled at its
            # first checkpoint, silently losing the settlement and leaking the Reservation
            # against the Window Quota until the whole Usage Window expires
            with anyio.CancelScope(shield=True):
                await response.aclose()
                await _settle_reservation(
                    ledger,
                    reservation,
                    failed=failed,
                    completed=completed,
                    usage=accumulator.usage,
                    input_chars=input_chars,
                    output_chars=accumulator.output_chars,
                )

    return _relay()


async def create_streaming_chat_response(
    *,
    chatbot_settings: ChatbotSettings,
    chatbot_api: ChatbotApi,
    body: CreateResponseRequest,
    request: Request,
    credentials_hash: str,
    user_id: UserID,
    product_name: ProductName,
    ledger: ChatboxUsageLedger | None = None,
) -> SseStreamingResponse | JSONResponse:
    """Opens a streamed chat completion and relays it as server-sent events.

    The Reservation placed by the admission control is reconciled against the actual usage
    reported on the stream's final chunk (or released on failure/abort).

    Raises:
        ChatbotRequestError: the Chatbox could not be reached or failed server-side.
        ChatboxRateLimitedError: admission rejected the API key's request rate.
        ProviderBudgetExhaustedError: admission hit the Global Budget Guard hard stop.
        ChatboxWindowQuotaExceededError: admission found the Window Quota full.
        UsageLedgerUnavailableError: admission could not trust Redis (fail-closed).
    """
    reservation = await _admit_and_reserve(
        ledger,
        credentials_hash=credentials_hash,
        user_id=user_id,
        product_name=product_name,
    )

    chatbot_session = ChatbotSession(
        _chatbot_settings=chatbot_settings,
        _api=chatbot_api,
    )
    try:
        upstream_response = await chatbot_session.stream_chat_completion(
            messages=[msg.to_domain_model() for msg in body.input],
            model=body.model,
            metadata=body.metadata or {},
            temperature=body.temperature,
            top_p=DEFAULT_TOP_P,
            response_format=body.to_chat_response_format(),
        )
    except ValidationError as exc:
        await _release_reservation(ledger, reservation, reason="request_rejected")
        # relay validation errors to caller to provide hints in the UI
        return await http422_error_handler(request, exc)
    except httpx.HTTPStatusError as exc:
        await _release_reservation(ledger, reservation, reason="chatbox_error")
        if is_4xx_client_error(exc.response.status_code):
            return _relay_downstream_client_error(exc.response)
        raise ChatbotRequestError from exc
    except httpx.HTTPError as exc:
        await _release_reservation(ledger, reservation, reason="chatbox_error")
        raise ChatbotRequestError from exc
    except BaseException:
        # client disconnect / shutdown while opening the stream: the metered relay below
        # is the only other owner of the Reservation and it never takes over from here
        await _release_reservation(ledger, reservation, reason="stream_open_failed")
        raise

    if ledger and reservation:
        input_chars = sum(len(msg.content) for msg in body.input)
        return SseStreamingResponse(
            _make_metered_sse_relay(
                response=upstream_response,
                request=request,
                ledger=ledger,
                reservation=reservation,
                input_chars=input_chars,
            )
        )

    return SseStreamingResponse(_relay_sse_response(upstream_response, request))


async def submit_background_chat_response(
    *,
    task_manager: TaskManager,
    body: CreateResponseRequest,
    credentials_hash: str,
    user_id: UserID,
    product_name: ProductName,
    ledger: ChatboxUsageLedger | None = None,
) -> ResponseObject:
    """Queues a background chat completion and returns its handle right away.

    The Reservation is placed before queueing so a request over quota never reaches the
    worker, and released if queueing itself fails. The worker owns it from there on.

    Raises:
        ChatboxRateLimitedError: admission rejected the API key's request rate.
        ProviderBudgetExhaustedError: admission hit the Global Budget Guard hard stop.
        ChatboxWindowQuotaExceededError: admission found the Window Quota full.
        UsageLedgerUnavailableError: admission could not trust Redis (fail-closed).
        Exception: the queueing failure itself, after the Reservation was refunded.
    """
    reservation = await _admit_and_reserve(
        ledger,
        credentials_hash=credentials_hash,
        user_id=user_id,
        product_name=product_name,
    )

    try:
        job = await submit_job(
            task_manager,
            execution_metadata=TaskExecutionMetadata(
                name=_TASK_NAME,
                queue=API_SERVER_CELERY_QUEUE_DEFAULT,
            ),
            owner_metadata=ApiServerOwnerMetadata(user_id=user_id, product_name=product_name),
            request=body,
            reservation_usd=reservation.amount_usd if reservation else None,
        )
    except BaseException:
        await _release_reservation(ledger, reservation, reason="submit_failed")
        raise

    return ResponseObject(
        id=f"{job.job_id}",
        background=True,
        model=body.model,
        status=ResponseStatus.QUEUED,
    )
