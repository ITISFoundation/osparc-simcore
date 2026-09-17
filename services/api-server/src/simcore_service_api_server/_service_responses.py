"""Business logic for the `/responses` streaming path (Controller-Service-Repository split)."""

from collections.abc import AsyncIterator

import httpx
from fastapi import Request
from pydantic import ValidationError
from servicelib.status_codes_utils import is_4xx_client_error
from starlette.responses import JSONResponse

from .core.settings import ChatbotSettings
from .exceptions.backend_errors import ChatbotRequestError
from .exceptions.handlers._utils import create_error_json_response
from .exceptions.handlers._validation_errors import http422_error_handler
from .models.basic_types import SseStreamingResponse
from .models.schemas.responses import CreateResponseRequest
from .services_http.chatbot import ChatbotApi, ChatbotSession


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
        errors = response.json().get("detail", response.text)
    except ValueError:
        errors = response.text
    if not isinstance(errors, list):
        errors = [errors]
    return create_error_json_response(*errors, status_code=response.status_code)


async def create_streaming_chat_response(
    *,
    chatbot_settings: ChatbotSettings,
    chatbot_api: ChatbotApi,
    body: CreateResponseRequest,
    request: Request,
) -> SseStreamingResponse | JSONResponse:
    """Opens a streamed chat completion and relays it as server-sent events."""
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
            response_format=body.to_chat_response_format(),
        )
    except ValidationError as exc:
        # relay validation errors to caller to provide hints in the UI
        return await http422_error_handler(request, exc)
    except httpx.HTTPStatusError as exc:
        if is_4xx_client_error(exc.response.status_code):
            return _relay_downstream_client_error(exc.response)
        raise ChatbotRequestError from exc
    except httpx.HTTPError as exc:
        raise ChatbotRequestError from exc
    return SseStreamingResponse(_relay_sse_response(upstream_response, request))
