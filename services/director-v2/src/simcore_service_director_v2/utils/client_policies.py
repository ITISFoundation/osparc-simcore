import functools
import logging
from typing import Coroutine

import httpx
from fastapi import HTTPException
from starlette import status
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)


def handle_retry(logger: logging.Logger):
    return retry(
        # SEE https://www.python-httpx.org/exceptions/
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.DEBUG),
    )


def handle_response(service_name: str, logger: logging.Logger):

    def decorator_func(request_func: Coroutine):

        @functools.wraps(request_func)
        async def wrapper_func(*args, **kwargs) -> httpx.Response:
            try:
                # TODO: assert signature!?
                resp: httpx.Response = await request_func(*args, **kwargs)

            except httpx.RequestError as err:
                logger.error(
                    "Failed request %s(%s, %s)", request_func.__name__, args, kwargs
                )
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"{service_name} is not reponsive",
                ) from err

            else:
                if httpx.codes.is_client_error(resp.status_code):
                    # Forward return clients errors
                    raise HTTPException(resp.status_code, detail=resp.reason_phrase)

                if httpx.codes.is_server_error(resp.status_code):  # 500<= code <=599
                    logger.error(
                        "%s service error %d [%s]: %s",
                        service_name,
                        resp.reason_phrase,
                        resp.status_code,
                        resp.text(),
                    )
                    # Server errors are retured as service not available?
                    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

            return resp

        return wrapper_func

    return decorator_func
