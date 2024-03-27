import logging
from typing import Any

import httpx
from fastapi import HTTPException
from httpx import codes
from starlette import status

logger = logging.getLogger(__name__)


def unenvelope_or_raise_error(resp: httpx.Response) -> list[Any] | dict[str, Any]:
    """
    Director responses are enveloped
    If successful response, we un-envelop it and return data as a dict
    If error, it raise an HTTPException
    """
    body = resp.json()

    assert "data" in body or "error" in body  # nosec
    data = body.get("data")
    error = body.get("error")

    if codes.is_server_error(resp.status_code):
        logger.error(
            "director error %d [%s]: %s",
            resp.status_code,
            resp.reason_phrase,
            error,
        )
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

    if codes.is_client_error(resp.status_code):
        msg = error or resp.reason_phrase
        raise HTTPException(resp.status_code, detail=msg)

    return data or {}
