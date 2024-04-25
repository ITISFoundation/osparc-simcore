import logging
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from functools import wraps
from typing import Any

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError

from ..models.schemas.errors import ErrorGet

_logger = logging.getLogger(__name__)


DEFAULT_BACKEND_SERVICE_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Too many requests",
        "model": ErrorGet,
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal server error",
        "model": ErrorGet,
    },
    status.HTTP_502_BAD_GATEWAY: {
        "description": "Unexpected error when communicating with backend service",
        "model": ErrorGet,
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Service unavailable",
        "model": ErrorGet,
    },
    status.HTTP_504_GATEWAY_TIMEOUT: {
        "description": "Request to a backend service timed out.",
        "model": ErrorGet,
    },
}


def service_exception_mapper(
    service_name: str,
    http_status_map: Mapping[int, tuple[int, Callable[[Any], str] | None]],
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with backend_service_exception_handler(
                service_name, http_status_map, **kwargs
            ):
                return await func(*args, **kwargs)

        return wrapper

    return decorator


@contextmanager
def backend_service_exception_handler(
    service_name: str,
    http_status_map: Mapping[int, tuple[int, Callable[[dict], str] | None]],
    **endpoint_kwargs,
):
    status_code: int
    detail: str
    headers: dict[str, str] = {}
    try:
        yield
    except ValidationError as exc:
        status_code = status.HTTP_502_BAD_GATEWAY
        detail = f"{service_name} service returned invalid response"
        _logger.exception(
            "Invalid data exchanged with %s service\n%s",
            service_name,
            f"{exc}",
        )
        raise HTTPException(
            status_code=status_code, detail=detail, headers=headers
        ) from exc
    except httpx.HTTPStatusError as exc:
        if status_detail_tuple := http_status_map.get(exc.response.status_code):
            status_code, detail_callback = status_detail_tuple
            if detail_callback is None:
                detail = f"{exc}."
            else:
                detail = f"{detail_callback(endpoint_kwargs)}."
        elif exc.response.status_code in {
            status.HTTP_429_TOO_MANY_REQUESTS,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_504_GATEWAY_TIMEOUT,
        }:
            status_code = exc.response.status_code
            detail = f"The {service_name} service was unavailable."
            if retry_after := exc.response.headers.get("Retry-After"):
                headers["Retry-After"] = retry_after
        else:
            status_code = status.HTTP_502_BAD_GATEWAY
            detail = f"Received unexpected response from {service_name}"

        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            _logger.exception(
                "Converted status code %s from %s service to status code %s\n%s",
                f"{exc.response.status_code}",
                service_name,
                f"{status_code}",
                f"{exc}",
            )
        raise HTTPException(
            status_code=status_code, detail=detail, headers=headers
        ) from exc
