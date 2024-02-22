import logging
from contextlib import contextmanager
from typing import Mapping

import httpx
from fastapi import HTTPException, status
from pydantic import ValidationError
from servicelib.error_codes import create_error_code

_logger = logging.getLogger(__name__)


@contextmanager
def backend_service_exception_handler(
    service_name: str, http_status_map: Mapping[int, tuple[int, str | None]]
):
    try:
        yield
    except ValidationError as exc:
        error_code = create_error_code(exc)
        _logger.exception(
            "Invalid data exchanged with webserver service [%s]",
            error_code,
            extra={"error_code": error_code},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{service_name} service returned invalid response. {error_code}",
        ) from exc

    except httpx.HTTPStatusError as exc:
        if code_detail_tuple := http_status_map.get(exc.response.status_code):
            status_code, detail = code_detail_tuple
            if detail is None:
                detail = exc.response.json()["errors"].join(", ")
            raise HTTPException(status_code=status_code, detail=detail) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Received unexpected response from {service_name}",
            )
