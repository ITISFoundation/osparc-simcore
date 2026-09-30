"""Business logic for the `/responses` routes (Controller-Service-Repository split).

Both paths enforce the Chatbox limits: the Rate Limit first (fail-open), then the Window
Quota and Global Budget Guard place a Reservation (fail-closed). The streaming path
reconciles that Reservation against the usage reported by the Chatbox; the background
path hands it over to the worker, which reconciles at task end.
"""

import logging
from collections.abc import AsyncIterator

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
    credential_hash: str,
    user_id: UserID,
    product_name: ProductName,
) -> Reservation | None:
    """Applies the Rate Limit (fail-open) and places a Reservation for the Window Quota
    and Global Budget Guard (fail-closed). Returns None when limits are not enforced."""
    if ledger is None:
        return None

    await ledger.acquire_rate_limit(credential_hash)
    return await ledger.admit_and_reserve(user_id=user_id, product_name=product_name)


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


def _parse_sse_event(raw_event: bytes) -> tuple[UsageRecord | None, int]:
    """Extracts the OpenAI-style aggregated `usage` object (sent on the final chunk,
    requested via stream_options) and the assistant text length from one SSE event."""
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
        usage_obj = payload.get("usage")
        if isinstance(usage_obj, dict) and isinstance(usage_obj.get("total_tokens"), int):
            usage = UsageRecord(
                total_tokens=usage_obj["total_tokens"],
                prompt_tokens=usage_obj.get("prompt_tokens"),
                completion_tokens=usage_obj.get("completion_tokens"),
            )
        for choice in payload.get("choices") or []:
            if (
                isinstance(choice, dict)
                and isinstance(choice.get("delta"), dict)
                and isinstance(content := choice["delta"].get("content"), str)
            ):
                text_chars += len(content)
    return usage, text_chars


def _make_metered_sse_relay(
    *,
    response: httpx.Response,
    request: Request,
    ledger: ChatboxUsageLedger,
    reservation: Reservation,
    input_chars: int,
) -> AsyncIterator[bytes]:
    async def _relay() -> AsyncIterator[bytes]:
        usage: UsageRecord | None = None
        output_chars = 0
        completed = False
        event_buffer = b""
        try:
            async for chunk in response.aiter_bytes():
                if await request.is_disconnected():
                    break
                # network chunks can split an SSE event: keep the tail until its terminator
                event_buffer += chunk
                *complete_events, event_buffer = event_buffer.split(b"\n\n")
                for raw_event in complete_events:
                    event_usage, text_chars = _parse_sse_event(raw_event)
                    usage = event_usage or usage
                    output_chars += text_chars
                yield chunk
            else:
                # stream ended normally: parse the trailing bytes as the last event
                if event_buffer:
                    event_usage, text_chars = _parse_sse_event(event_buffer)
                    usage = event_usage or usage
                    output_chars += text_chars
                completed = True
        except BaseException:
            # timeout / upstream abort mid-stream: refund the Reservation (the
            # released-reservations counter makes the uncounted burn visible)
            await ledger.release(reservation, reason="stream_error")
            raise
        finally:
            await response.aclose()

        if not completed:
            # client disconnected before the completion finished
            await ledger.release(reservation, reason="client_abort")
            return

        if usage is None:
            # the Chatbox is expected to always report usage; if it did not, estimate
            # from text length and never fail the request over accounting
            usage = UsageRecord.estimated_from_text(input_chars=input_chars, output_chars=output_chars)
        await ledger.reconcile(reservation, usage)

    return _relay()


async def create_streaming_chat_response(
    *,
    chatbot_settings: ChatbotSettings,
    chatbot_api: ChatbotApi,
    body: CreateResponseRequest,
    request: Request,
    credential_hash: str,
    user_id: UserID,
    product_name: ProductName,
    ledger: ChatboxUsageLedger | None = None,
) -> SseStreamingResponse | JSONResponse:
    """Opens a streamed chat completion and relays it as server-sent events.

    The Reservation placed by the admission control is reconciled against the actual usage
    reported on the stream's final chunk (or released on failure/abort).
    """
    reservation = await _admit_and_reserve(
        ledger,
        credential_hash=credential_hash,
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
        if reservation and ledger:
            await ledger.release(reservation, reason="request_rejected")
        # relay validation errors to caller to provide hints in the UI
        return await http422_error_handler(request, exc)
    except httpx.HTTPStatusError as exc:
        if reservation and ledger:
            await ledger.release(reservation, reason="upstream_error")
        if is_4xx_client_error(exc.response.status_code):
            return _relay_downstream_client_error(exc.response)
        raise ChatbotRequestError from exc
    except httpx.HTTPError as exc:
        if reservation and ledger:
            await ledger.release(reservation, reason="upstream_error")
        raise ChatbotRequestError from exc

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
    credential_hash: str,
    user_id: UserID,
    product_name: ProductName,
    ledger: ChatboxUsageLedger | None = None,
) -> ResponseObject:
    """Queues a background chat completion and returns its handle right away.

    The Reservation is placed before queueing so a request over quota never reaches the
    worker, and released if queueing itself fails. The worker owns it from there on.
    """
    reservation = await _admit_and_reserve(
        ledger,
        credential_hash=credential_hash,
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
        if reservation and ledger:
            await ledger.release(reservation, reason="submit_failed")
        raise

    return ResponseObject(
        id=f"{job.job_id}",
        background=True,
        model=body.model,
        status=ResponseStatus.QUEUED,
    )
