import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Mapping

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError
from servicelib.error_codes import create_error_code
from simcore_service_api_server.models.basic_types import HTTPExceptionModel

_logger = logging.getLogger(__name__)


SERVICE_DEFAULT_STATUS_CODES: dict[int | str, dict[str, Any]] | None = {
    status.HTTP_502_BAD_GATEWAY: {
        "description": "Returned when an unexpected error occured when communicating with a backend service.",
        "model": HTTPExceptionModel,
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Returned when the service (or a backend service) is unavailable. In this case a 'Retry-After' header might also be returned.",
        "model": HTTPExceptionModel,
    },
    status.HTTP_429_TOO_MANY_REQUESTS: {
        "description": "Returned if too many requests have been sent to the service (or a backend service).",
        "model": HTTPExceptionModel,
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
    try:
        yield
    except ValidationError as exc:
        error_code = create_error_code(exc)
        _logger.exception(
            "Invalid data exchanged with %s service [%s] ",
            service_name,
            error_code,
            extra={"error_code": error_code},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{service_name} service returned invalid response. {error_code}",
        ) from exc

    except httpx.HTTPStatusError as exc:
        if status_detail_tuple := http_status_map.get(exc.response.status_code):
            status_code, detail_callback = status_detail_tuple
            if detail_callback is None:
                detail = f"{exc}"
            else:
                detail = detail_callback(endpoint_kwargs)
            raise HTTPException(status_code=status_code, detail=detail) from exc
        if exc.response.status_code in {
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_429_TOO_MANY_REQUESTS,
        }:
            headers = {}
            if "Retry-After" in exc.response.headers:
                headers["Retry-After"] = exc.response.headers["Retry-After"]
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"The {service_name} service was unavailable",
                headers=headers,
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Received unexpected response from {service_name}",
        ) from exc
