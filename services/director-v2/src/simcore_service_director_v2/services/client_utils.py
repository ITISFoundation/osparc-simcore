import functools
import logging
from typing import Coroutine

import httpx
from fastapi import HTTPException
from starlette import status
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger(__name__)


retry_handler = retry(wait=wait_fixed(2), stop=stop_after_attempt(3))


async def error_handler(request_func: Coroutine):
    @functools.wraps(request_func)
    async def wrapper(*args, **kwargs) -> httpx.Response:
        try:
            resp: httpx.Response = await request_func(*args, **kwargs)

            if httpx.codes.is_client_error(resp.status_code):
                # Forward return clients errors
                raise HTTPException(resp.status_code, detail=resp.reason_phrase)

            elif httpx.codes.is_server_error(resp.status_code):  # 500<= code <=599
                logger.error(
                    "Director service error %d [%s]: %s",
                    resp.reason_phrase,
                    resp.status_code,
                    resp.text(),
                )
                # Server errors are retured as service not available?
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as err:
            logger.exception(
                "Failed client request %s(%s, %s)", request_func.__name__, args, kwargs
            )
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE) from err

        return resp

    return wrapper
