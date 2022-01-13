""" Collection of decorators for httpx request functions

    Each decorator implements a specific feature on the request workflow:
    - retrial
    - error handling
    - TODO: circuit breaker?
    - TODO: diagnostic tracker?
    - TODO: cache?
"""

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
    """
    Retry policy after connection timeout or a network error

    SEE https://www.python-httpx.org/exceptions/
    """
    return retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        wait=wait_fixed(2),
        stop=stop_after_attempt(3),
        reraise=True,
        before_sleep=before_sleep_log(logger, logging.DEBUG),
    )


def handle_errors(service_name: str, logger: logging.Logger):
    """
    Handles different types of errors and transform them into error reponses

    - httpx errors -> logged + respond with HTTP_503_SERVICE_UNAVAILABLE
    - response client error -> forward response
    - response server error -> logged + responds with HTTP_503_SERVICE_UNAVAILABLE
    """

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
                    detail=f"{service_name} is not responsive",
                ) from err

            else:
                # status response errors
                if httpx.codes.is_client_error(resp.status_code):
                    raise HTTPException(resp.status_code, detail=resp.reason_phrase)

                if httpx.codes.is_server_error(resp.status_code):  # i.e. 5XX error
                    logger.error(
                        "%s service error %s [%s]: %s",
                        service_name,
                        resp.reason_phrase,
                        f"{resp.status_code=}",
                        resp.text,
                    )
                    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE)

            return resp

        return wrapper_func

    return decorator_func
