import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Mapping

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError
from servicelib.error_codes import create_error_code
from simcore_service_api_server.models.schemas.errors import ErrorGet

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
    error_code: str
    detail: str
    headers: dict[str, str] = {}
    try:
        yield
    except ValidationError as exc:
        error_code = create_error_code(exc)
        status_code = status.HTTP_502_BAD_GATEWAY
        detail = f"{service_name} service returned invalid response. {error_code}"
        _logger.exception(
            "Invalid data exchanged with %s service [%s]: %s",
            service_name,
            error_code,
            f"{exc}",
            extra={"error_code": error_code},
        )
        raise HTTPException(
            status_code=status_code, detail=detail, headers=headers
        ) from exc
    except httpx.HTTPStatusError as exc:
        error_code = create_error_code(exc)
        if status_detail_tuple := http_status_map.get(exc.response.status_code):
            status_code, detail_callback = status_detail_tuple
            if detail_callback is None:
                detail = f"{exc}. {error_code}"
            else:
                detail = f"{detail_callback(endpoint_kwargs)}. {error_code}"
        elif exc.response.status_code in {
            status.HTTP_429_TOO_MANY_REQUESTS,
            status.HTTP_503_SERVICE_UNAVAILABLE,
        }:
            status_code = exc.response.status_code
            detail = f"The {service_name} service was unavailable. {error_code}"
            if retry_after := exc.response.headers.get("Retry-After"):
                headers["Retry-After"] = retry_after
        else:
            status_code = status.HTTP_502_BAD_GATEWAY
            detail = f"Received unexpected response from {service_name}. {error_code}"

        if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            _logger.exception(
                "Converted status code %s from %s service to %s [%s]: %s",
                f"{exc.response.status_code}",
                service_name,
                f"{status_code}",
                error_code,
                f"{exc}",
                extra={"error_code": error_code},
            )
        raise HTTPException(
            status_code=status_code, detail=detail, headers=headers
        ) from exc
